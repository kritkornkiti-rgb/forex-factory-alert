#!/bin/bash
# ==============================================================================
# Forex Factory Red & Orange Folder News Launcher
# คลิกสองครั้งเพื่อเปิดใช้งานบน macOS
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# เช็ค Virtual Environment
if [ -d ".venv" ]; then
    PYTHON_CMD="./.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

clear
echo "====================================================================="
echo "🔴 Forex Factory Red & Orange Folder News Tracker & Telegram Alert"
echo "   ตารางและระบบแจ้งเตือนข่าวกล่องแดง & กล่องส้ม (เวลาไทย UTC+7)"
echo "====================================================================="
echo ""
echo "กรุณาเลือกเมนูการใช้งาน:"
echo "  1) 🌐 เปิด Web Dashboard บนเบราว์เซอร์ (เวลานับถอยหลัง & เสียงเตือน)"
echo "  2) 📊 ดูตารางข่าวกล่องแดงและกล่องส้มใน Terminal ตอนนี้"
echo "  3) 📅 ดูเฉพาะข่าววันนี้ (Today Only)"
echo "  4) 📋 ดูข้อความสรุปข่าว (พร้อมคัดลอกลง LINE / Telegram)"
echo "  5) 🤖 ตั้งค่าเชื่อมต่อ Telegram Bot (ใส่ Token & Chat ID)"
echo "  6) 📲 ส่งสรุปข่าววันนี้เข้า Telegram ทันที"
echo "  7) 🚨 เปิดระบบเฝ้าระวังแจ้งเตือนอัตโนมัติ 24 ชม. (Telegram + Desktop)"
echo "  8) 🔔 ทดสอบส่งข้อความเข้า Telegram"
echo "  0) ❌ ออกจากการทำงาน"
echo ""
read -p "กดเลือกหมายเลข [1-8 หรือ 0] (ค่าเริ่มต้น: 1): " choice

choice=${choice:-1}

case $choice in
    1)
        echo ""
        echo "🚀 กำลังเปิด Web Dashboard..."
        $PYTHON_CMD forex_news.py --web
        ;;
    2)
        echo ""
        $PYTHON_CMD forex_news.py --table
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    3)
        echo ""
        $PYTHON_CMD forex_news.py --table --today
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    4)
        echo ""
        $PYTHON_CMD forex_news.py --summary --today
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    5)
        echo ""
        $PYTHON_CMD forex_news.py --setup-telegram
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    6)
        echo ""
        $PYTHON_CMD forex_news.py --send-telegram-summary --today
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    7)
        echo ""
        $PYTHON_CMD forex_news.py --monitor
        ;;
    8)
        echo ""
        $PYTHON_CMD forex_news.py --test-telegram
        echo ""
        read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
        ;;
    0)
        echo "ออกจากการทำงาน"
        exit 0
        ;;
    *)
        echo "ตัวเลือกไม่ถูกต้อง กำลังเปิด Web Dashboard..."
        $PYTHON_CMD forex_news.py --web
        ;;
esac
