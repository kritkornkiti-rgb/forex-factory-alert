#!/bin/bash
# ==============================================================================
# Forex News 24/7 Background Monitor Launcher
# ดับเบิ้ลคลิกเพื่อรันระบบเฝ้าระวังเบื้องหลังตลอด 24 ชม.
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# เช็ค Virtual Environment
if [ -d ".venv" ]; then
    PYTHON_CMD="./.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

mkdir -p data

# ตรวจสอบว่ากำลังทำงานอยู่แล้วหรือไม่
PID=$(pgrep -f "forex_news.py --monitor")
if [ -n "$PID" ]; then
    echo "⚠️ ระบบเฝ้าระวังกำลังทำงานอยู่แล้ว (PID: $PID)"
    echo "ดู Log ล่าสุดได้ที่: data/forex_monitor.log"
    read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
    exit 0
fi

nohup $PYTHON_CMD -u forex_news.py --monitor > data/forex_monitor.log 2>&1 &
NEW_PID=$!

echo "====================================================================="
echo "🚀 เปิดระบบเฝ้าระวังแจ้งเตือน Forex Factory 24 ชม. สำเร็จแล้ว!"
echo "====================================================================="
echo "• Process ID (PID): $NEW_PID"
echo "• ระบบกำลังทำงานอยู่เบื้องหลัง (ปิดหน้าต่างนี้ได้เลย บอทจะยังทำงานต่อ)"
echo "• การแจ้งเตือน: ส่งเข้า Telegram และหน้าจอ Mac อัตโนมัติ"
echo "• ดูบันทึกการทำงาน (Log): data/forex_monitor.log"
echo "====================================================================="
echo ""
read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
