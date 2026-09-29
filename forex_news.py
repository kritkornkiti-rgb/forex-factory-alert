#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forex Factory Red & Orange Folder News Tracker & Telegram Alert System
- ดึงข้อมูลปฏิทินเศรษฐกิจจาก Forex Factory (Faireconomy CDN)
- แปลงเวลาเป็นเวลาประเทศไทย (UTC+7) อัตโนมัติ
- รองรับทั้งข่าวกล่องแดง (High Impact) และกล่องส้ม (Medium Impact)
- ระบบแจ้งเตือนเรียลไทม์ผ่าน Telegram Bot, Desktop (macOS), LINE, Discord
- ตารางแสดงผลสวยงามทั้งใน Terminal และ Web Dashboard
"""

import os
import sys
import json
import time
import ssl
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone

# กำหนด Timezone ประเทศไทย (UTC+7)
try:
    import zoneinfo
    BANGKOK_TZ = zoneinfo.ZoneInfo("Asia/Bangkok")
except Exception:
    BANGKOK_TZ = timezone(timedelta(hours=7))

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_FILE = DATA_DIR / "forex_calendar_cache.json"
NOTIFIED_FILE = DATA_DIR / "forex_notified_events.json"
CONFIG_FILE = DATA_DIR / "forex_news_config.json"
ENV_FILE = BASE_DIR / ".env"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# URL ของ Forex Factory (Faireconomy CDN)
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_TTL_HOURS = 2  # แคชข้อมูลไว้ 2 ชม. เพื่อป้องกัน Cloudflare Rate Limit (HTTP 429)

CURRENCY_FLAGS = {
    "USD": "🇺🇸 USD",
    "EUR": "🇪🇺 EUR",
    "GBP": "🇬🇧 GBP",
    "JPY": "🇯🇵 JPY",
    "AUD": "🇦🇺 AUD",
    "CAD": "🇨🇦 CAD",
    "CHF": "🇨🇭 CHF",
    "NZD": "🇳🇿 NZD",
    "CNY": "🇨🇳 CNY",
}

THAI_DAYS = {
    "Monday": "วันจันทร์",
    "Tuesday": "วันอังคาร",
    "Wednesday": "วันพุธ",
    "Thursday": "วันพฤหัสบดี",
    "Friday": "วันศุกร์",
    "Saturday": "วันเสาร์",
    "Sunday": "วันอาทิตย์",
}

THAI_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."
]


# ==============================================================================
# Helper to Load Credentials
# ==============================================================================
def load_credentials():
    """โหลด Token และ Chat ID จาก .env และ data/forex_news_config.json"""
    forex_env_token = os.getenv("FOREX_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    creds = {
        "telegram_token": forex_env_token,
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "line_token": os.getenv("LINE_TOKEN", ""),
        "discord_webhook": os.getenv("DISCORD_WEBHOOK_URL", "")
    }

    # อ่านจาก .env
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k == "FOREX_TELEGRAM_BOT_TOKEN" and v:
                            creds["telegram_token"] = v
                        elif k == "TELEGRAM_BOT_TOKEN" and not creds["telegram_token"] and v:
                            creds["telegram_token"] = v
                        elif k == "TELEGRAM_CHAT_ID" and v:
                            creds["telegram_chat_id"] = v
                        elif k == "LINE_TOKEN" and v:
                            creds["line_token"] = v
                        elif k == "DISCORD_WEBHOOK_URL" and v:
                            creds["discord_webhook"] = v
        except Exception:
            pass

    # อ่านจาก forex_news_config.json
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("telegram_token"):
                    creds["telegram_token"] = saved["telegram_token"]
                if saved.get("telegram_chat_id"):
                    creds["telegram_chat_id"] = saved["telegram_chat_id"]
        except Exception:
            pass

    return creds


def save_telegram_credentials(token: str, chat_id: str):
    """บันทึก Telegram Token และ Chat ID ลง .env และ forex_news_config.json"""
    token = token.strip()
    chat_id = chat_id.strip()

    # 1. บันทึก forex_news_config.json
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg["telegram_token"] = token
    cfg["telegram_chat_id"] = chat_id
    cfg["telegram_enabled"] = True
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    # 2. บันทึกหรืออัปเดต .env
    env_lines = []
    has_token = False
    has_chat = False
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("FOREX_TELEGRAM_BOT_TOKEN="):
                    env_lines.append(f"FOREX_TELEGRAM_BOT_TOKEN={token}\n")
                    has_token = True
                elif line.startswith("TELEGRAM_CHAT_ID="):
                    env_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
                    has_chat = True
                else:
                    env_lines.append(line)
    if not has_token:
        env_lines.append(f"FOREX_TELEGRAM_BOT_TOKEN={token}\n")
    if not has_chat:
        env_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(env_lines)

    os.environ["FOREX_TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_CHAT_ID"] = chat_id


# ==============================================================================
# Forex Factory Calendar Engine
# ==============================================================================
class ForexCalendar:
    def __init__(self):
        self.ssl_context = self._create_ssl_context()

    def _create_ssl_context(self):
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(cafile=certifi.where())
        except Exception:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def load_cache(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] ไม่สามารถอ่านแคชเดิมได้: {e}")
        return None

    def save_cache(self, data):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] ไม่สามารถบันทึกแคชได้: {e}")

    def fetch_data(self, force_refresh=False):
        # 1. ตรวจสอบว่ามีแคชที่ยังไม่หมดอายุหรือไม่
        if not force_refresh and CACHE_FILE.exists():
            file_age_seconds = time.time() - CACHE_FILE.stat().st_mtime
            if file_age_seconds < CACHE_TTL_HOURS * 3600:
                cached_data = self.load_cache()
                if cached_data:
                    return cached_data, "cache"

        # 2. ดาวน์โหลดข้อมูลใหม่จาก Forex Factory
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        req = urllib.request.Request(FEED_URL, headers=headers)

        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=15) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8")
                    data = json.loads(raw_data)
                    self.save_cache(data)
                    return data, "live"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("\n[⚠️ แจ้งเตือน] เว็บไซต์ Forex Factory มีการจำกัดความถี่ (Rate Limit 429)")
                cached_data = self.load_cache()
                if cached_data:
                    print("--> สลับไปใช้ข้อมูลล่าสุดจากไฟล์แคช (ข้อมูลยังถูกต้องสำหรับสัปดาห์นี้)")
                    return cached_data, "cache_fallback"
                else:
                    raise Exception("Forex Factory Rate Limited และยังไม่มีไฟล์แคชในระบบ กรุณารอสักครู่แล้วลองใหม่")
            raise
        except Exception as e:
            cached_data = self.load_cache()
            if cached_data:
                print(f"\n[⚠️ ไม่สามารถเชื่อมต่อเน็ตได้: {e}] สลับไปใช้ข้อมูลจากแคช")
                return cached_data, "cache_fallback"
            raise

    def get_events(self, impact_filter=("High", "Medium"), currency_filter=None, force_refresh=False):
        raw_events, source = self.fetch_data(force_refresh=force_refresh)
        now_bkk = datetime.now(BANGKOK_TZ)

        processed = []
        for idx, item in enumerate(raw_events):
            impact = item.get("impact", "")
            if impact_filter and impact not in impact_filter:
                continue

            country = item.get("country", "")
            if currency_filter and country != currency_filter:
                continue

            date_str = item.get("date", "")
            try:
                # แปลง ISO format เป็น datetime พร้อม timezone
                dt = datetime.fromisoformat(date_str)
                dt_bkk = dt.astimezone(BANGKOK_TZ)
            except Exception:
                continue

            diff = dt_bkk - now_bkk
            total_minutes = int(diff.total_seconds() // 60)

            # คำนวณข้อความนับถอยหลัง
            if total_minutes < 0:
                past_min = abs(total_minutes)
                if past_min < 60:
                    countdown = f"ผ่านไป {past_min} นาที"
                elif past_min < 1440:
                    countdown = f"ผ่านไป {past_min // 60} ชม."
                else:
                    countdown = f"ผ่านไป {past_min // 1440} วัน"
                status_code = "PAST"
            elif total_minutes <= 15:
                icon = "🔴" if impact == "High" else "🟠"
                countdown = f"{icon} ด่วน! อีก {total_minutes} นาที"
                status_code = "IMMINENT"
            elif total_minutes <= 60:
                countdown = f"⚠️ อีก {total_minutes} นาที"
                status_code = "SOON"
            elif total_minutes <= 1440:
                h = total_minutes // 60
                m = total_minutes % 60
                countdown = f"⏳ อีก {h} ชม. {m} นาที"
                status_code = "TODAY"
            else:
                days = total_minutes // 1440
                h = (total_minutes % 1440) // 60
                countdown = f"📅 อีก {days} วัน {h} ชม."
                status_code = "UPCOMING"

            thai_day = THAI_DAYS.get(dt_bkk.strftime("%A"), dt_bkk.strftime("%A"))
            date_formatted = f"{thai_day} {dt_bkk.day} {THAI_MONTHS[dt_bkk.month]} {dt_bkk.year}"
            time_formatted = dt_bkk.strftime("%H:%M น.")

            event_id = f"{country}_{dt_bkk.strftime('%Y%m%d_%H%M')}_{item.get('title')}"

            processed.append({
                "id": event_id,
                "title": item.get("title", ""),
                "country": country,
                "currency_label": CURRENCY_FLAGS.get(country, country),
                "impact": impact,
                "datetime_bkk": dt_bkk,
                "date_bkk_str": date_formatted,
                "time_bkk_str": time_formatted,
                "timestamp_ms": int(dt_bkk.timestamp() * 1000),
                "forecast": item.get("forecast") or "-",
                "previous": item.get("previous") or "-",
                "diff_minutes": total_minutes,
                "countdown": countdown,
                "status_code": status_code,
                "is_today": dt_bkk.date() == now_bkk.date(),
            })

        processed.sort(key=lambda x: x["datetime_bkk"])
        return processed, source


# ==============================================================================
# Terminal Table & Display
# ==============================================================================
def render_terminal_table(events, source_info=""):
    now_bkk = datetime.now(BANGKOK_TZ)
    current_time_str = now_bkk.strftime("%A %d/%m/%Y เวลา %H:%M:%S (UTC+7)")

    # ANSI Colors
    RED = "\033[91m"
    ORANGE = "\033[38;5;208m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    print("\n" + "=" * 96)
    print(f"{BOLD}{RED}🔴 ตารางข่าวกล่องแดง (High) & 🟠 กล่องส้ม (Medium) FOREX FACTORY{RESET}")
    print(f"{CYAN}🕒 เวลาปัจจุบัน: {current_time_str} | ข้อมูล: {source_info}{RESET}")
    print("=" * 96)

    header = f"{BOLD}{'วัน/เวลา (ไทย)':<18} | {'ระดับ':<10} | {'สกุล':<8} | {'ชื่อข่าว (News Title)':<30} | {'คาดการณ์':<9} | {'ก่อนหน้า':<9} | {'สถานะ':<15}{RESET}"
    print(header)
    print("-" * 96)

    if not events:
        print("  ไม่พบรายการข่าวที่ตรงกับเงื่อนไขในสัปดาห์นี้")
        print("=" * 96 + "\n")
        return

    current_day = None
    for ev in events:
        ev_day = ev["date_bkk_str"]
        if ev_day != current_day:
            current_day = ev_day
            print(f"\n{BOLD}{CYAN}📅 {current_day}{RESET}")
            print("·" * 96)

        dt_str = f"{ev['time_bkk_str']}"
        impact_badge = "🔴 แดง" if ev["impact"] == "High" else "🟠 ส้ม"
        country = ev["currency_label"]
        title = ev["title"][:28]
        forecast = ev["forecast"][:8]
        previous = ev["previous"][:8]
        countdown = ev["countdown"]

        # สีตามระดับความรุนแรงและสถานะ
        if ev["status_code"] == "IMMINENT":
            row_color = BOLD + RED
        elif ev["impact"] == "High":
            row_color = RED
        elif ev["impact"] == "Medium":
            row_color = ORANGE
        elif ev["status_code"] == "PAST":
            row_color = DIM
        else:
            row_color = RESET

        print(f"{row_color}{dt_str:<18} | {impact_badge:<10} | {country:<8} | {title:<30} | {forecast:<9} | {previous:<9} | {countdown:<15}{RESET}")

    print("=" * 96 + "\n")


# ==============================================================================
# Telegram Message Formatting
# ==============================================================================
def format_telegram_event_alert(ev, stage="15m"):
    """จัดรูปแบบข้อความเตือนข่าวส่งเข้า Telegram แบบ HTML หรูหราและชัดเจน"""
    is_high = ev.get("impact") == "High"
    icon = "🔴" if is_high else "🟠"
    impact_name = "กล่องแดง (High Impact)" if is_high else "กล่องส้ม (Medium Impact)"

    if stage == "60m":
        badge = "⏳ <b>แจ้งเตือนล่วงหน้า 1 ชั่วโมง</b>"
    elif stage == "15m":
        badge = "🚨 <b>เตือนด่วน! ข่าวจะออกในอีก 15 นาที</b>"
    else:
        badge = "📢 <b>ถึงเวลาประกาศผลข่าวแล้ว!</b>"

    lines = [
        f"{icon} {badge}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>ระดับความแรง:</b> {icon} {impact_name}",
        f"⏰ <b>เวลาประกาศ:</b> <b>{ev['time_bkk_str']}</b> (เวลาไทย UTC+7)",
        f"📅 <b>วันที่:</b> {ev['date_bkk_str']}",
        f"🌍 <b>สกุลเงิน:</b> {ev['currency_label']}",
        f"📰 <b>ข่าวเศรษฐกิจ:</b> <b>{ev['title']}</b>",
        f"🎯 <b>ตัวเลขคาดการณ์ (Forecast):</b> <code>{ev.get('forecast', '-')}</code>",
        f"📦 <b>ตัวเลขก่อนหน้า (Previous):</b> <code>{ev.get('previous', '-')}</code>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if is_high:
        lines.append("⚠️ <b>คำเตือน:</b> <i>ข่าวกล่องแดงกราฟอาจสวิงแรงและ Spread ถ่างสูง แนะนำลดความเสี่ยงหรือหลีกเลี่ยงการเปิดออเดอร์ชนข่าว</i>")
    else:
        lines.append("ℹ️ <b>คำแนะนำ:</b> <i>ข่าวกล่องส้มมีผลกระทบปานกลาง อาจสร้างแรงกระเพื่อมระยะสั้นในคู่เงินที่เกี่ยวข้อง</i>")

    return "\n".join(lines)


def format_telegram_summary(events, today_only=True):
    """สร้างข้อความสรุปข่าวกล่องแดงและกล่องส้มสำหรับส่งเข้า Telegram"""
    now_bkk = datetime.now(BANGKOK_TZ)
    if today_only:
        filtered = [e for e in events if e.get("is_today")]
        title = f"📋 <b>สรุปข่าวกล่องแดง & กล่องส้มวันนี้</b>\n📅 <i>{now_bkk.strftime('%d/%m/%Y')} (เวลาไทย UTC+7)</i>"
    else:
        filtered = events
        title = f"📋 <b>ตารางข่าวกล่องแดง & กล่องส้มสัปดาห์นี้</b>\n<i>อัปเดต ณ วันที่ {now_bkk.strftime('%d/%m/%Y')}</i>"

    if not filtered:
        return f"{title}\n\n✅ วันนี้ไม่มีข่าวกล่องแดงหรือกล่องส้ม"

    lines = [
        title,
        f"🕒 เวลาปัจจุบัน: {now_bkk.strftime('%H:%M น.')}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    reds = [e for e in filtered if e.get("impact") == "High"]
    oranges = [e for e in filtered if e.get("impact") == "Medium"]

    if reds:
        lines.append("\n🔴 <b>[กล่องแดง] High Impact (ความผันผวนสูง):</b>")
        for ev in reds:
            lines.append(f"• <b>{ev['time_bkk_str']}</b> {ev['currency_label']} | <b>{ev['title']}</b>")
            lines.append(f"  └ คาด: <code>{ev['forecast']}</code> | ก่อนหน้า: <code>{ev['previous']}</code> ({ev['countdown']})")

    if oranges:
        lines.append("\n🟠 <b>[กล่องส้ม] Medium Impact (ความผันผวนปานกลาง):</b>")
        for ev in oranges:
            lines.append(f"• <b>{ev['time_bkk_str']}</b> {ev['currency_label']} | {ev['title']}")
            lines.append(f"  └ คาด: <code>{ev['forecast']}</code> | ก่อนหน้า: <code>{ev['previous']}</code> ({ev['countdown']})")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔔 <i>ระบบเฝ้าระวังจะแจ้งเตือนล่วงหน้า 15 นาทีก่อนข่าวออกทุกรายการ</i>")
    return "\n".join(lines)


def get_ssl_context():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ==============================================================================
# Telegram API Dispatcher & Setup
# ==============================================================================
def send_telegram_alert(token: str, chat_id: str, message: str) -> bool:
    """ส่งข้อความเข้า Telegram ผ่าน Bot API"""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[!] Telegram API HTTP Error ({e.code}): {err_msg}")
        return False
    except Exception as e:
        print(f"[!] Telegram Alert Error: {e}")
        return False


def test_telegram_connection(token: str, chat_id: str):
    """ทดสอบเชื่อมต่อ Telegram ตรวจสอบ Bot name และส่งข้อความทดสอบ"""
    print("\n🔍 กำลังตรวจสอบความถูกต้องของ Telegram Bot Token...")
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                bot_user = data["result"].get("username", "UnknownBot")
                bot_name = data["result"].get("first_name", "Bot")
                print(f"✅ บอทถูกต้อง: {bot_name} (@{bot_user})")
            else:
                print("❌ Token ไม่ถูกต้องหรือไม่สามารถเชื่อมต่อกับ Telegram ได้")
                return False
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบ Token: {e}")
        return False

    print(f"📨 กำลังส่งข้อความทดสอบไปยัง Chat ID: {chat_id} ...")
    test_msg = (
        "🎉 <b>ยินดีด้วย! เชื่อมต่อระบบแจ้งเตือนสำเร็จ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔴 <b>Forex Factory Alert System พร้อมทำงานแล้ว!</b>\n"
        "ระบบจะแจ้งเตือนข่าวกล่องแดง (High) และกล่องส้ม (Medium) ให้คุณล่วงหน้า 15 นาทีอัตโนมัติ 🚀"
    )
    ok = send_telegram_alert(token, chat_id, test_msg)
    if ok:
        print("✅ ส่งข้อความทดสอบเข้า Telegram สำเร็จแล้ว! (กรุณาเปิดดูในแอป Telegram ของคุณ)")
        return True
    else:
        print("❌ ไม่สามารถส่งข้อความได้ กรุณาตรวจสอบ Chat ID หรือตรวจสอบว่าได้กด /start ที่บอทหรือยัง")
        return False


def setup_telegram_wizard():
    """เมนูอินเตอร์แอคทีฟช่วยเหลือการตั้งค่า Telegram Bot แบบ Step-by-Step"""
    creds = load_credentials()
    current_token = creds.get("telegram_token", "")
    current_chat = creds.get("telegram_chat_id", "")

    print("\n" + "=" * 65)
    print("🤖 ตั้งค่าระบบแจ้งเตือนผ่าน TELEGRAM BOT")
    print("=" * 65)
    print("วิธีเตรียมข้อมูล:")
    print("  1. ค้นหา @BotFather บน Telegram -> พิมพ์ /newbot เพื่อสร้างบอท")
    print("     แล้วคัดลอก HTTP API Token มาใส่")
    print("  2. ค้นหา @userinfobot บน Telegram -> กด /start เพื่อดูเลข Chat ID")
    print("  3. ⚠️ สำคัญมาก: ต้องกดปุ่ม 'Start' คุยกับบอทของคุณเองอย่างน้อย 1 ครั้ง")
    print("-" * 65)

    if current_token:
        print(f"Token ปัจจุบัน: {current_token[:8]}...{current_token[-6:]}")
    token_input = input(f"ใส่ TELEGRAM_BOT_TOKEN [{current_token if current_token else 'กดว่างหากไม่มี'}]: ").strip()
    token = token_input if token_input else current_token

    if current_chat:
        print(f"Chat ID ปัจจุบัน: {current_chat}")
    chat_input = input(f"ใส่ TELEGRAM_CHAT_ID [{current_chat if current_chat else 'กดว่างหากไม่มี'}]: ").strip()
    chat_id = chat_input if chat_input else current_chat

    if not token or not chat_id:
        print("❌ ไม่ได้ระบุ Token หรือ Chat ID ยกเลิกการตั้งค่า")
        return False

    success = test_telegram_connection(token, chat_id)
    if success:
        save_telegram_credentials(token, chat_id)
        print(f"\n💾 บันทึกการตั้งค่าลง .env และ data/alert_config.json เรียบร้อยแล้ว!")
        return True
    else:
        retry = input("\nต้องการบันทึกค่าไว้ก่อนหรือไม่? (y/n) [y]: ").strip().lower()
        if retry != "n":
            save_telegram_credentials(token, chat_id)
            print("💾 บันทึกค่าเรียบร้อยแล้ว (คุณสามารถทดสอบใหม่อีกครั้งได้)")
        return False


# ==============================================================================
# Mac Notification, LINE, Discord
# ==============================================================================
def send_macos_notification(title, message, sound="Hero"):
    if sys.platform != "darwin":
        return False
    try:
        clean_title = title.replace('"', '\\"')
        clean_msg = message.replace('"', '\\"')
        script = f'display notification "{clean_msg}" with title "{clean_title}" sound name "{sound}"'
        subprocess.run(["osascript", "-e", script], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def send_line_alert(token, message):
    if not token:
        return False
    url = "https://notify-api.line.me/api/notify"
    data = urllib.parse.urlencode({"message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def dispatch_event_alert(ev, stage="15m"):
    """ส่งการแจ้งเตือนข่าวไปยัง Telegram และ Desktop"""
    is_high = ev.get("impact") == "High"
    badge = "🔴 กล่องแดง" if is_high else "🟠 กล่องส้ม"
    title = f"{badge} ในอีก 15 นาที ({ev['currency_label']})" if stage == "15m" else f"{badge} ({ev['currency_label']})"
    body = f"{ev['time_bkk_str']}: {ev['title']}\nคาดการณ์: {ev['forecast']} | ก่อนหน้า: {ev['previous']}"

    print(f"\n[📢 ALERT] {title} - {body}")

    # 1. Desktop macOS
    send_macos_notification(title, body, sound="Submarine" if is_high else "Hero")

    # 2. Telegram Alert (จัดรูปแบบ HTML สวยงาม)
    creds = load_credentials()
    if creds["telegram_token"] and creds["telegram_chat_id"]:
        tg_text = format_telegram_event_alert(ev, stage=stage)
        send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], tg_text)

    # 3. LINE
    if creds["line_token"]:
        send_line_alert(creds["line_token"], f"\n{title}\n{body}")


# ==============================================================================
# Background Monitor / Daemon
# ==============================================================================
def run_monitor(check_interval=60, impacts=("High", "Medium")):
    """
    วนลูปตรวจสอบข่าวกล่องแดงและกล่องส้มทุกๆ check_interval วินาที:
    - แจ้งเตือนล่วงหน้า 60 นาที (กล่องแดง)
    - แจ้งเตือนล่วงหน้า 15 นาที (กล่องแดง + กล่องส้ม)
    - แจ้งเตือนทันทีที่ข่าวออก (0 นาที)
    - สรุปข่าวประจำวันตอนเช้า 08:00 น. ส่งเข้า Telegram
    """
    cal = ForexCalendar()
    creds = load_credentials()
    has_tg = bool(creds["telegram_token"] and creds["telegram_chat_id"])

    print("\n" + "=" * 70)
    print("🚀 เริ่มต้นระบบเฝ้าระวังข่าวกล่องแดง 🔴 และกล่องส้ม 🟠 FOREX FACTORY")
    print(f"🕒 ตรวจสอบเวลาทุกๆ {check_interval} วินาที | แปลงเวลาเป็นเวลาไทย (UTC+7)")
    if has_tg:
        print("📲 สถานะ Telegram: เปิดใช้งานแล้ว (พร้อมส่งการแจ้งเตือนเข้ามือถือ)")
    else:
        print("⚠️ สถานะ Telegram: ยังไม่ได้ตั้งค่า (จะแจ้งเตือนบนหน้าจอคอมพิวเตอร์แทน)")
        print("   -> แนะนำรัน 'python3 forex_news.py --setup-telegram' เพื่อรับการแจ้งเตือนเข้ามือถือ")
    print("=" * 70)
    print("กด Ctrl+C เพื่อหยุดการทำงาน\n")

    notified = {}
    if NOTIFIED_FILE.exists():
        try:
            with open(NOTIFIED_FILE, "r") as f:
                notified = json.load(f)
        except Exception:
            notified = {}

    last_morning_date = None

    while True:
        try:
            now = datetime.now(BANGKOK_TZ)
            events, source = cal.get_events(impact_filter=impacts)

            # สรุปข่าวเช้า 08:00
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 8 and now.minute == 0 and last_morning_date != today_str:
                last_morning_date = today_str
                if has_tg:
                    summary_tg = format_telegram_summary(events, today_only=True)
                    send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], summary_tg)
                send_macos_notification("สรุปข่าวเศรษฐกิจวันนี้", "มีรายการข่าวกล่องแดงและกล่องส้มวันนี้ ตรวจสอบได้ในระบบ")

            for ev in events:
                diff_m = ev["diff_minutes"]
                ev_id = ev["id"]
                is_high = ev["impact"] == "High"

                # 1. เตือนล่วงหน้า 60 นาที (เฉพาะกล่องแดง High Impact)
                if is_high and 55 <= diff_m <= 60 and f"{ev_id}_60m" not in notified:
                    notified[f"{ev_id}_60m"] = True
                    dispatch_event_alert(ev, stage="60m")

                # 2. เตือนล่วงหน้า 15 นาที (ทั้งกล่องแดง High และกล่องส้ม Medium)
                elif 10 <= diff_m <= 15 and f"{ev_id}_15m" not in notified:
                    notified[f"{ev_id}_15m"] = True
                    dispatch_event_alert(ev, stage="15m")

                # 3. เตือนเมื่อถึงเวลาข่าวออก (ระหว่าง -1 ถึง 2 นาที)
                elif -1 <= diff_m <= 2 and f"{ev_id}_0m" not in notified:
                    notified[f"{ev_id}_0m"] = True
                    dispatch_event_alert(ev, stage="0m")

            # บันทึกสถานะการแจ้งเตือน
            with open(NOTIFIED_FILE, "w") as f:
                json.dump(notified, f)

            # แสดงสถานะ Heartbeat เบาๆ ใน Terminal ทุกๆ 5 นาที
            if now.second < check_interval and now.minute % 5 == 0:
                upcoming = [e for e in events if e['diff_minutes'] > 0]
                next_txt = f"{upcoming[0]['currency_label']} {upcoming[0]['title']} (อีก {upcoming[0]['diff_minutes']} น.)" if upcoming else "ไม่มีข่าวในสัปดาห์นี้"
                print(f"[{now.strftime('%H:%M:%S')}] 🟢 ระบบกำลังเฝ้าระวัง... ข่าวถัดไป: {next_txt}")

            time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n👋 สิ้นสุดการเฝ้าระวัง")
            break
        except Exception as e:
            print(f"[!] Monitor Loop Error: {e}")
            time.sleep(check_interval)


# ==============================================================================
# Web Dashboard HTTP Server
# ==============================================================================
def start_web_server(port=5050, auto_open=True):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import webbrowser

    cal = ForexCalendar()
    html_file = BASE_DIR / "forex_news_dashboard.html"

    class ForexHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/news" or self.path.startswith("/api/news?"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                try:
                    events, source = cal.get_events(impact_filter=("High", "Medium"))
                    serializable = []
                    for e in events:
                        item = dict(e)
                        item["datetime_bkk"] = item["datetime_bkk"].isoformat()
                        serializable.append(item)

                    res = {
                        "status": "success",
                        "updated_at": datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                        "source": source,
                        "events": serializable
                    }
                    self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                except Exception as ex:
                    err = {"status": "error", "message": str(ex)}
                    self.wfile.write(json.dumps(err).encode("utf-8"))
                return

            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if html_file.exists():
                    with open(html_file, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.wfile.write(b"<h1>Dashboard file not found.</h1>")
                return

            return super().do_GET()

        def do_POST(self):
            if self.path == "/api/refresh":
                cal.fetch_data(force_refresh=True)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "refreshed"}')
                return

            if self.path == "/api/test-alert":
                send_macos_notification("ทดสอบการแจ้งเตือน Forex Factory", "ระบบแจ้งเตือนทำงานได้สมบูรณ์แบบ!", sound="Hero")
                creds = load_credentials()
                if creds["telegram_token"] and creds["telegram_chat_id"]:
                    send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], "🔔 <b>ทดสอบแจ้งเตือนจาก Web Dashboard!</b>")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "alert_sent"}')
                return

            self.send_response(404)
            self.end_headers()

    server = HTTPServer(("0.0.0.0", port), ForexHandler)
    url = f"http://localhost:{port}"
    print(f"\n🌐 เปิดหน้าเว็บ Dashboard สำเร็จที่: {url}")
    print("กด Ctrl+C เพื่อปิดเว็บเซิร์ฟเวอร์\n")

    if auto_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 ปิดเว็บเซิร์ฟเวอร์เรียบร้อย")
        server.server_close()


# ==============================================================================
# Main CLI Entry Point
def run_cron_check(window_minutes=25):
    """
    สำหรับรันใน GitHub Actions (Serverless Cloud Execution):
    - รันแบบ Single-run ตรวจสอบข่าวที่กำลังจะออกในอีก window_minutes นาที
    - ส่งแจ้งเตือนล่วงหน้าเข้า Telegram
    - ถ้าเป็นเวลาเช้า 07:45 - 08:30 น. จะส่งสรุปข่าวประจำวัน
    """
    cal = ForexCalendar()
    creds = load_credentials()
    if not creds["telegram_token"] or not creds["telegram_chat_id"]:
        print("⚠️ ไม่พบ Telegram credentials ในระบบ")
        return

    now = datetime.now(BANGKOK_TZ)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🤖 GitHub Actions กำลังตรวจสอบข่าว Forex Factory...")

    events, source = cal.get_events(impact_filter=("High", "Medium"), force_refresh=True)

    # 1. ตรวจสอบการส่งสรุปเช้า (ระหว่าง 07:45 ถึง 08:30 น. เวลาไทย = 00:45 ถึง 01:30 UTC)
    if now.hour == 8 and now.minute <= 30:
        print("🌅 กำลังส่งสรุปข่าวประจำวันรอบเช้าเข้า Telegram...")
        summary = format_telegram_summary(events, today_only=True)
        send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], summary)

    # 2. ตรวจสอบข่าวที่จะออกในอีก 0 ถึง window_minutes นาที
    upcoming = []
    for ev in events:
        diff_m = ev["diff_minutes"]
        if 0 <= diff_m <= window_minutes:
            upcoming.append(ev)

    if upcoming:
        print(f"🚨 พบข่าวสำคัญกำลังจะออก {len(upcoming)} รายการ:")
        for ev in upcoming:
            stage = "15m" if ev["diff_minutes"] <= 20 else "60m"
            print(f"  • {ev['time_bkk_str']} {ev['currency_label']} {ev['title']} (อีก {ev['diff_minutes']} น.)")
            tg_text = format_telegram_event_alert(ev, stage=stage)
            send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], tg_text)
            time.sleep(1)
        print("✅ ส่งแจ้งเตือนเข้า Telegram เรียบร้อยแล้ว")
    else:
        print(f"✅ ไม่มีข่าวกล่องแดง/ส้ม ในช่วง {window_minutes} นาทีข้างหน้า")


# ==============================================================================
# Main CLI Entry Point
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Forex Factory Red & Orange News Tracker & Telegram Alert System")
    parser.add_argument("--table", action="store_true", help="แสดงตารางข่าวใน Terminal (ทั้งกล่องแดงและส้ม)")
    parser.add_argument("--web", action="store_true", help="เปิด Web Dashboard บนเบราว์เซอร์")
    parser.add_argument("--monitor", action="store_true", help="รันระบบเฝ้าระวังแจ้งเตือนอัตโนมัติ (Telegram + Desktop)")
    parser.add_argument("--cron-check", action="store_true", help="สำหรับรันใน GitHub Actions (ตรวจสอบข่าวรอบปัจจุบันแล้วจบงาน)")
    parser.add_argument("--window", type=int, default=25, help="ช่วงเวลานาทีสำหรับตรวจสอบใน Cron (ค่าเริ่มต้น 25 นาที)")
    parser.add_argument("--setup-telegram", action="store_true", help="ตั้งค่าเชื่อมต่อ Telegram Bot")
    parser.add_argument("--test-telegram", action="store_true", help="ทดสอบส่งข้อความเข้า Telegram")
    parser.add_argument("--send-telegram-summary", action="store_true", help="ส่งสรุปข่าววันนี้เข้า Telegram ทันที")
    parser.add_argument("--summary", action="store_true", help="แสดงข้อความสรุปสำหรับส่งเข้า LINE / Telegram")
    parser.add_argument("--today", action="store_true", help="กรองเฉพาะข่าววันนี้")
    parser.add_argument("--currency", type=str, default=None, help="กรองเฉพาะสกุลเงิน เช่น USD, EUR, GBP")
    parser.add_argument("--red-only", action="store_true", help="ดูเฉพาะกล่องแดงเท่านั้น")
    parser.add_argument("--refresh", action="store_true", help="บังคับดึงข้อมูลใหม่จากเว็บ (ไม่อ่านจากแคช)")
    parser.add_argument("--port", type=int, default=5050, help="พอร์ตสำหรับ Web Dashboard (ค่าเริ่มต้น 5050)")

    args = parser.parse_args()

    # 1. เมนูตั้งค่า Telegram
    if args.setup_telegram:
        setup_telegram_wizard()
        return

    # 2. เมดสอบ Telegram
    if args.test_telegram:
        creds = load_credentials()
        if not creds["telegram_token"] or not creds["telegram_chat_id"]:
            print("⚠️ ยังไม่ได้ตั้งค่า Telegram กรุณารัน: python3 forex_news.py --setup-telegram")
            return
        test_telegram_connection(creds["telegram_token"], creds["telegram_chat_id"])
        return

    # 3. รัน Cron Check (สำหรับ GitHub Actions)
    if args.cron_check:
        run_cron_check(window_minutes=args.window)
        return

    # 4. รัน Background Monitor
    if args.monitor:
        impacts = ("High",) if args.red_only else ("High", "Medium")
        run_monitor(impacts=impacts)
        return

    # 4. รัน Web Dashboard
    if args.web:
        start_web_server(port=args.port, auto_open=True)
        return

    # เตรียมข้อมูลสำหรับ Table / Summary
    impacts = ("High",) if args.red_only else ("High", "Medium")
    cal = ForexCalendar()
    try:
        events, source = cal.get_events(
            impact_filter=impacts,
            currency_filter=args.currency.upper() if args.currency else None,
            force_refresh=args.refresh
        )
    except Exception as e:
        print(f"\n[❌ เกิดข้อผิดพลาด] ไม่สามารถดึงข้อมูลข่าวได้: {e}")
        return

    if args.today:
        events = [e for e in events if e["is_today"]]

    # 5. ส่งสรุปเข้า Telegram ทันที
    if args.send_telegram_summary:
        creds = load_credentials()
        if not creds["telegram_token"] or not creds["telegram_chat_id"]:
            print("⚠️ ยังไม่ได้ตั้งค่า Telegram กรุณารัน: python3 forex_news.py --setup-telegram")
            return
        msg = format_telegram_summary(events, today_only=args.today)
        print("📨 กำลังส่งสรุปข่าวเข้า Telegram...")
        if send_telegram_alert(creds["telegram_token"], creds["telegram_chat_id"], msg):
            print("✅ ส่งสรุปข่าวเข้า Telegram สำเร็จแล้ว!")
        else:
            print("❌ ไม่สามารถส่งสรุปข่าวได้")
        return

    # 6. แสดงสรุป Text
    if args.summary:
        print(format_telegram_summary(events, today_only=args.today))
        return

    # 7. ค่าเริ่มต้น: แสดงตาราง Terminal
    render_terminal_table(events, source_info=f"Forex Factory ({source})")


if __name__ == "__main__":
    main()
