"""
AI bottrade - Notification & Alert Dispatcher
Sends real-time trading signals and SL/TP alerts via:
1. macOS Native Desktop Notifications (Banner + Sound - No API key needed!)
2. Telegram Bot (Instant push to smartphone / desktop)
3. Discord Webhook
4. LINE Notify
"""
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional
import requests

from src.config import DATA_DIR, format_price, format_currency_price
from src.trade_setup import TradeSetup

logger = logging.getLogger("AI-bottrade-notifier")


class AlertNotifier:
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (DATA_DIR / "alert_config.json")
        self.config = {
            "macos_enabled": True,
            "telegram_enabled": False,
            "telegram_token": "",
            "telegram_chat_id": "",
            "discord_enabled": False,
            "discord_webhook_url": "",
            "line_enabled": False,
            "line_token": ""
        }
        self.load_config()

    def load_config(self):
        """Loads alert credentials from disk and environment variables"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                logger.warning(f"Failed to read alert config: {e}")

        # Check environment variables (ideal for Docker / Cloud VPS)
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            self.config["telegram_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
            self.config["telegram_enabled"] = True
        if os.environ.get("TELEGRAM_CHAT_ID"):
            self.config["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
            self.config["telegram_enabled"] = True
        if os.environ.get("DISCORD_WEBHOOK_URL"):
            self.config["discord_webhook_url"] = os.environ["DISCORD_WEBHOOK_URL"]
            self.config["discord_enabled"] = True
        if os.environ.get("LINE_TOKEN"):
            self.config["line_token"] = os.environ["LINE_TOKEN"]
            self.config["line_enabled"] = True

    def save_config(self):
        """Saves alert credentials to disk"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
            logger.info("Saved alert settings.")
        except Exception as e:
            logger.error(f"Error saving alert config: {e}")

    def send_macos_notification(self, title: str, message: str, sound: str = "Glass"):
        """Displays a native macOS banner notification with sound"""
        if not self.config.get("macos_enabled", True):
            return
        try:
            # Escape double quotes
            safe_title = title.replace('"', '\\"')
            safe_msg = message.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound}"'
            subprocess.run(["osascript", "-e", script], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Sent macOS notification: {title}")
        except Exception as e:
            logger.debug(f"macOS notification failed: {e}")

    def send_telegram(self, message: str) -> bool:
        """Sends an HTML formatted message via Telegram Bot"""
        token = self.config.get("telegram_token", "").strip()
        chat_id = self.config.get("telegram_chat_id", "").strip()
        if not token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, json=payload, timeout=8)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def send_discord(self, message: str) -> bool:
        """Sends an alert message to a Discord Webhook"""
        webhook_url = self.config.get("discord_webhook_url", "").strip()
        if not webhook_url:
            return False

        try:
            resp = requests.post(webhook_url, json={"content": message}, timeout=8)
            return resp.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return False

    def send_line(self, message: str) -> bool:
        """Sends an alert message via LINE Notify"""
        token = self.config.get("line_token", "").strip()
        if not token:
            return False

        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.post(url, headers=headers, data={"message": message}, timeout=8)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"LINE notify error: {e}")
            return False

    def broadcast_text(self, title: str, message: str):
        """Broadcasts text alert to all enabled channels"""
        self.send_macos_notification(title, message)
        full_text = f"🚨 <b>{title}</b>\n\n{message}"
        if self.config.get("telegram_enabled"):
            self.send_telegram(full_text)
        if self.config.get("discord_enabled"):
            self.send_discord(f"**{title}**\n{message}")
        if self.config.get("line_enabled"):
            self.send_line(f"\n{title}\n{message}")

    def broadcast_trade_setup(self, setup: TradeSetup):
        """Formats and broadcasts a rich Trade Setup alert"""
        if setup.status != "ACTIVE_SETUP":
            return

        icon = "🟢" if "BUY" in setup.direction else "🔴"
        title = f"{icon} AI bottrade: {setup.direction} Signal ({setup.asset})"

        p_entry = format_currency_price(setup.asset, setup.entry_price)
        p_sl = format_currency_price(setup.asset, setup.stop_loss)
        p_tp1 = format_currency_price(setup.asset, setup.take_profit_1)
        p_tp2 = format_currency_price(setup.asset, setup.take_profit_2)

        htf_line_tg = ""
        htf_line_dc = ""
        htf_line_mac = ""
        if setup.htf_timeframe and setup.htf_bias:
            htf_icon = "🟢" if "BULL" in setup.htf_bias.upper() else ("🔴" if "BEAR" in setup.htf_bias.upper() else "⚪")
            htf_line_tg = f"🔭 <b>HTF Trend ({setup.htf_timeframe}):</b> {setup.htf_bias} {htf_icon}\n"
            htf_line_dc = f"🔭 **HTF Trend ({setup.htf_timeframe}):** {setup.htf_bias}\n"
            htf_line_mac = f"HTF ({setup.htf_timeframe}): {setup.htf_bias} | "

        candle_line_tg = f"🕯️ <b>การยืนยันแท่งเทียน:</b> {setup.candlestick_pattern}\n" if setup.candlestick_pattern else ""
        candle_line_dc = f"🕯️ **การยืนยันแท่งเทียน:** {setup.candlestick_pattern}\n" if setup.candlestick_pattern else ""

        mac_msg = (
            f"Asset: {setup.asset} ({setup.timeframe})\n"
            f"{htf_line_mac}Conf: {setup.ai_confidence:.1%} | SMC: {setup.confluence_score}/{setup.total_confluences}\n"
            f"Entry: {p_entry} | SL: {p_sl} | TP1: {p_tp1}"
        )
        self.send_macos_notification(title, mac_msg)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Format passed confluences checklist item-by-item
        confluence_lines_tg = []
        confluence_lines_dc = []
        for conf in setup.confluence_list:
            if conf.get("passed"):
                name = conf.get("name", "")
                detail = conf.get("detail", "")
                if "โครงสร้างตลาด" in name:
                    label = "โครงสร้างตลาด"
                elif "โซนราคาได้เปรียบ" in name:
                    label = "โซนราคาได้เปรียบ"
                elif "โซนสถาบัน" in name:
                    label = "โซนสถาบัน (OB)"
                elif "ช่องว่างราคา" in name:
                    label = "ช่องว่างราคา (FVG)"
                elif "กวาดสภาพคล่อง" in name:
                    label = "กวาดสภาพคล่อง (Sweep)"
                elif "ความมั่นใจของ AI" in name:
                    label = "ความมั่นใจ AI"
                elif "แท่งเทียนยืนยัน" in name:
                    label = "การยืนยันแท่งเทียน"
                else:
                    label = name.split("(")[0].strip()
                confluence_lines_tg.append(f"  ✅ <b>{label}:</b> {detail}")
                confluence_lines_dc.append(f"  ✅ **{label}:** {detail}")

        confluences_block_tg = "\n".join(confluence_lines_tg) if confluence_lines_tg else "  - ไม่มีข้อมูล"
        confluences_block_dc = "\n".join(confluence_lines_dc) if confluence_lines_dc else "  - ไม่มีข้อมูล"

        telegram_msg = (
            f"🎯 <b>AI bottrade: สัญญาณเทรดใหม่ (TRADE SIGNAL)</b> 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>สินทรัพย์:</b> {setup.asset} ({setup.timeframe})\n"
            f"⚡ <b>คำสั่ง:</b> <b>{setup.direction}</b>\n"
            f"🕐 <b>เวลา:</b> <code>{now_str}</code>\n"
            f"{htf_line_tg}"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ <b>SMC Confluence ผ่านเกณฑ์ ({setup.confluence_score}/{setup.total_confluences} ข้อ):</b>\n"
            f"{confluences_block_tg}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ราคาเข้า (Entry):</b> <code>{p_entry}</code>\n"
            f"🛑 <b>Stop Loss (SL):</b> <code>{p_sl}</code> (-{setup.sl_pct:.2f}%)\n"
            f"🏆 <b>Take Profit 1:</b> <code>{p_tp1}</code> (+{setup.tp1_pct:.2f}%) [R:R 1:{setup.tp1_rr:.1f}]\n"
            f"🚀 <b>Take Profit 2:</b> <code>{p_tp2}</code> (+{setup.tp2_pct:.2f}%) [R:R 1:{setup.tp2_rr:.1f}]\n"
            f"💼 <b>ขนาดไม้แนะนำ:</b> <code>{setup.recommended_size:.4f} units</code> (${setup.position_value:,.2f})"
        )

        discord_msg = (
            f"🚨 **[AI bottrade SIGNAL ALERT]**\n"
            f"**Asset:** {setup.asset} ({setup.timeframe})\n"
            f"**Signal:** {setup.direction} (Confidence: {setup.ai_confidence:.1%})\n"
            f"{htf_line_dc}"
            f"**SMC Confluence ({setup.confluence_score}/{setup.total_confluences}):**\n"
            f"{confluences_block_dc}\n"
            f"🎯 **Entry:** {p_entry}\n"
            f"🛑 **SL:** {p_sl} (-{setup.sl_pct:.2f}%)\n"
            f"🏆 **TP1:** {p_tp1} (+{setup.tp1_pct:.2f}%)\n"
            f"🚀 **TP2:** {p_tp2} (+{setup.tp2_pct:.2f}%)\n"
            f"💼 **Size:** {setup.recommended_size:.4f} units"
        )

        if self.config.get("telegram_enabled"):
            self.send_telegram(telegram_msg)
        if self.config.get("discord_enabled"):
            self.send_discord(discord_msg)
        if self.config.get("line_enabled"):
            line_msg = f"\n[AI Signal] {setup.direction} for {setup.asset}\nEntry: {p_entry}\nSL: {p_sl}\nTP1: {p_tp1}\nTP2: {p_tp2}"
            self.send_line(line_msg)

    def broadcast_position_closed(self, trade: dict):
        """Formats and broadcasts a rich Position Closed notification with full entry/exit tracking"""
        # User requested: Do not send paper trade notifications (only signal alerts)
        if not self.config.get("notify_paper_trade", False):
            return
        asset = trade.get("asset", "")
        tf = trade.get("timeframe", "")
        direction = trade.get("direction", "BUY (LONG)")
        entry_time = trade.get("entry_time", "")
        exit_time = trade.get("exit_time", "")
        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        duration_str = trade.get("duration_str", "N/A")
        net_pnl = trade.get("net_pnl", 0.0)
        pnl_pct = trade.get("net_pnl_pct", 0.0)
        exit_reason = trade.get("exit_reason", "")
        size = trade.get("size", 0.0)

        p_entry = format_currency_price(asset, entry_price)
        p_exit = format_currency_price(asset, exit_price)

        is_win = net_pnl >= 0
        pnl_badge = "🟢 กำไร (PROFIT)" if is_win else "🔴 ขาดทุน (LOSS)"
        reason_label = "🏆 TAKE PROFIT (แตะเป้าหมาย)" if exit_reason == "TAKE_PROFIT" else "🛑 STOP LOSS (ชนจุดตัดขาดทุน)"
        dir_badge = "🟢 BUY (LONG)" if "BUY" in direction.upper() else "🔴 SELL (SHORT)"

        telegram_msg = (
            f"📢 <b>AI bottrade: ปิดสถานะออเดอร์ ({reason_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>สินทรัพย์:</b> {asset} ({tf})\n"
            f"⚡ <b>ประเภทออเดอร์:</b> <b>{dir_badge}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 <b>เวลาเปิดออเดอร์ (Entry Time):</b> <code>{entry_time}</code>\n"
            f"🎯 <b>ราคาเปิด (Entry Price):</b> <code>{p_entry}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <b>เวลาปิดออเดอร์ (Exit Time):</b> <code>{exit_time}</code>\n"
            f"🏁 <b>ราคาปิด (Exit Price):</b> <code>{p_exit}</code>\n"
            f"⏱️ <b>ระยะเวลาถือครอง:</b> <b>{duration_str}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>ผลลัพธ์สุทธิ:</b> <b>{'+' if is_win else ''}{net_pnl:,.2f} USD ({pnl_pct:+.2f}%)</b> {pnl_badge}\n"
            f"💼 <b>ขนาดออเดอร์:</b> <code>{size:.4f} units</code>"
        )

        title = f"📢 Position Closed: {asset} ({tf}) - {'Profit' if is_win else 'Loss'}"
        mac_msg = f"{dir_badge} closed at {p_exit} ({reason_label})\nPnL: {'+' if is_win else ''}{net_pnl:.2f} USD ({pnl_pct:+.2f}%)\nEntry: {entry_time}"
        self.send_macos_notification(title, mac_msg)

        if self.config.get("telegram_enabled"):
            self.send_telegram(telegram_msg)
        if self.config.get("discord_enabled"):
            self.send_discord(telegram_msg.replace("<b>", "**").replace("</b>", "**").replace("<code>", "`").replace("</code>", "`"))

    def broadcast_position_opened(self, pos: dict, asset: str, tf: str):
        """Formats and broadcasts a detailed Position Opened notification"""
        # User requested: Do not send paper trade notifications (only signal alerts)
        if not self.config.get("notify_paper_trade", False):
            return
        direction = pos.get("direction", "BUY (LONG)")
        entry_time = pos.get("entry_time", "")
        entry_price = pos.get("entry_price", 0.0)
        sl_price = pos.get("sl_price", 0.0)
        tp_price = pos.get("tp_price", 0.0)
        size = pos.get("size", 0.0)
        confidence = pos.get("confidence", 0.5)

        p_entry = format_currency_price(asset, entry_price)
        p_sl = format_currency_price(asset, sl_price)
        p_tp = format_currency_price(asset, tp_price)

        dir_badge = "🟢 BUY (LONG)" if "BUY" in direction.upper() else "🔴 SELL (SHORT)"

        candle_pattern = pos.get("candlestick_pattern")
        candle_line = f"🕯️ <b>การยืนยันแท่งเทียน:</b> {candle_pattern}\n" if candle_pattern else ""

        telegram_msg = (
            f"⚡ <b>AI bottrade: เปิดสถานะใหม่ (POSITION OPENED)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>สินทรัพย์:</b> {asset} ({tf})\n"
            f"⚡ <b>ทิศทาง:</b> <b>{dir_badge}</b>\n"
            f"🕐 <b>เวลาเปิดออเดอร์:</b> <code>{entry_time}</code>\n"
            f"{candle_line}"
            f"🎯 <b>ราคาเปิด (Entry):</b> <code>{p_entry}</code>\n"
            f"🛑 <b>Stop Loss (SL):</b> <code>{p_sl}</code>\n"
            f"🏆 <b>Take Profit (TP):</b> <code>{p_tp}</code>\n"
            f"💼 <b>ขนาดไม้:</b> <code>{size:.4f} units</code>\n"
            f"🧠 <b>ความมั่นใจ AI:</b> {confidence:.1%}"
        )

        title = f"⚡ Position Opened: {asset} ({tf}) - {direction}"
        mac_msg = f"{direction} opened at {p_entry}\nSL: {p_sl} | TP: {p_tp}\nTime: {entry_time}"
        self.send_macos_notification(title, mac_msg)

        if self.config.get("telegram_enabled"):
            self.send_telegram(telegram_msg)
        if self.config.get("discord_enabled"):
            self.send_discord(telegram_msg.replace("<b>", "**").replace("</b>", "**").replace("<code>", "`").replace("</code>", "`"))

    def test_alert(self) -> dict:
        """Sends a test alert to all configured channels"""
        results = {}
        # Test macOS
        try:
            self.send_macos_notification("🤖 AI bottrade Test", "การแจ้งเตือนบน macOS ทำงานได้ปกติ!")
            results["macos"] = "Success"
        except Exception as e:
            results["macos"] = f"Failed: {e}"

        # Test Telegram
        if self.config.get("telegram_enabled"):
            ok = self.send_telegram("🧪 <b>AI bottrade:</b> ทดสอบการเชื่อมต่อ Telegram สำเร็จเรียบร้อย! ระบบพร้อมส่งสัญญาณแล้ว 🚀")
            results["telegram"] = "Success" if ok else "Failed (Check Token / Chat ID)"

        # Test Discord
        if self.config.get("discord_enabled"):
            ok = self.send_discord("🧪 **AI bottrade:** Discord Webhook connection successful! 🚀")
            results["discord"] = "Success" if ok else "Failed (Check Webhook URL)"

        # Test LINE
        if self.config.get("line_enabled"):
            ok = self.send_line("\n[AI bottrade] ทดสอบการเชื่อมต่อ LINE Notify สำเร็จเรียบร้อย! 🚀")
            results["line"] = "Success" if ok else "Failed (Check LINE Token)"

        return results
