"""
AI bottrade - Notification & Alert Dispatcher
Sends real-time trading signals and SL/TP alerts via:
1. macOS Native Desktop Notifications (Banner + Sound - No API key needed!)
2. Telegram Bot (Instant push to smartphone / desktop)
3. Discord Webhook
4. LINE Notify
"""
import json
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional
import requests

from src.config import DATA_DIR
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

        mac_msg = (
            f"Asset: {setup.asset} ({setup.timeframe})\n"
            f"Entry: ${setup.entry_price:,.2f} | SL: ${setup.stop_loss:,.2f}\n"
            f"TP1: ${setup.take_profit_1:,.2f} (1:{setup.tp1_rr:.1f}) | Conf: {setup.ai_confidence:.1%}"
        )
        self.send_macos_notification(title, mac_msg)

        telegram_msg = (
            f"🚨 <b>AI bottrade SIGNAL ALERT</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>สินทรัพย์:</b> {setup.asset} ({setup.timeframe})\n"
            f"⚡ <b>สัญญาณ:</b> <b>{setup.direction}</b>\n"
            f"🧠 <b>ความมั่นใจ AI:</b> {setup.ai_confidence:.1%}\n"
            f"🏛️ <b>SMC Confluence:</b> {setup.confluence_score}/{setup.total_confluences}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ราคาเข้า (Entry):</b> <code>${setup.entry_price:,.2f}</code>\n"
            f"🛑 <b>Stop Loss (SL):</b> <code>${setup.stop_loss:,.2f}</code> (-{setup.sl_pct:.2f}%)\n"
            f"🏆 <b>Take Profit 1:</b> <code>${setup.take_profit_1:,.2f}</code> (+{setup.tp1_pct:.2f}%) [R:R 1:{setup.tp1_rr:.1f}]\n"
            f"🚀 <b>Take Profit 2:</b> <code>${setup.take_profit_2:,.2f}</code> (+{setup.tp2_pct:.2f}%) [R:R 1:{setup.tp2_rr:.1f}]\n"
            f"💼 <b>ขนาดไม้แนะนำ:</b> <code>{setup.recommended_size:.4f} units</code> (${setup.position_value:,.2f})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>{setup.rationale_th}</i>"
        )

        discord_msg = (
            f"🚨 **[AI bottrade SIGNAL ALERT]**\n"
            f"**Asset:** {setup.asset} ({setup.timeframe})\n"
            f"**Signal:** {setup.direction} (Confidence: {setup.ai_confidence:.1%})\n"
            f"🎯 **Entry:** ${setup.entry_price:,.2f}\n"
            f"🛑 **SL:** ${setup.stop_loss:,.2f} (-{setup.sl_pct:.2f}%)\n"
            f"🏆 **TP1:** ${setup.take_profit_1:,.2f} (+{setup.tp1_pct:.2f}%)\n"
            f"🚀 **TP2:** ${setup.take_profit_2:,.2f} (+{setup.tp2_pct:.2f}%)\n"
            f"💼 **Size:** {setup.recommended_size:.4f} units\n"
            f"_{setup.rationale_th}_"
        )

        if self.config.get("telegram_enabled"):
            self.send_telegram(telegram_msg)
        if self.config.get("discord_enabled"):
            self.send_discord(discord_msg)
        if self.config.get("line_enabled"):
            line_msg = f"\n[AI Signal] {setup.direction} for {setup.asset}\nEntry: ${setup.entry_price:,.2f}\nSL: ${setup.stop_loss:,.2f}\nTP1: ${setup.take_profit_1:,.2f}\nTP2: ${setup.take_profit_2:,.2f}"
            self.send_line(line_msg)

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
