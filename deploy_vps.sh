#!/bin/bash
# ==============================================================================
# Forex Factory Alert - 1-Click VPS Deployment Script
# รันคำสั่งนี้บน Linux VPS (Ubuntu/Debian) เพื่อติดตั้งและเปิดใช้งาน 24 ชม.
# ==============================================================================

set -e

echo "=================================================================="
echo "🚀 ติดตั้งระบบแจ้งเตือน Forex Factory 24 ชม. บน Linux VPS"
echo "=================================================================="

# 1. ตรวจสอบและสร้างโฟลเดอร์ทำงาน
APP_DIR="/root/forex-factory-alert"
if [ ! -d "$APP_DIR" ]; then
    APP_DIR="$(pwd)"
fi
cd "$APP_DIR"

# 2. ติดตั้ง Python3 (ถ้ายังไม่มี)
apt-get update -y >/dev/null 2>&1 || true
apt-get install -y python3 python3-pip git curl >/dev/null 2>&1 || true

# 3. ตรวจสอบไฟล์ .env
if [ ! -f .env ]; then
    echo "⚠️ ไม่พบไฟล์ .env กำลังสร้างไฟล์ใหม่..."
    cat <<EOF > .env
FOREX_TELEGRAM_BOT_TOKEN=8919277790:AAHuUgy5Ao3fR3EfFK9tjFDCJWGaRdxTzkc
TELEGRAM_CHAT_ID=1265496331
EOF
    echo "✅ สร้าง .env พร้อมใส่ Token สำเร็จ"
fi

# 4. ตั้งค่า systemd Service เพื่อให้รันตลอด 24 ชม. และเริ่มทำงานอัตโนมัติเมื่อเปิดเครื่อง
cat <<EOF > /etc/systemd/system/forex-news.service
[Unit]
Description=Forex Factory 24/7 News Alert Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 -u forex_news.py --monitor
Restart=always
RestartSec=10
StandardOutput=append:/var/log/forex-news.log
StandardError=append:/var/log/forex-news-err.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable forex-news
systemctl restart forex-news

echo ""
echo "=================================================================="
echo "🎉 บอทแจ้งเตือนข่าว Forex Factory ทำงานบน VPS เรียบร้อยแล้ว!"
echo "• สถานะ: รันตลอด 24 ชม. 365 วัน (ระบบจะรีสตาร์ทตัวเองอัตโนมัติหากเน็ตหลุด)"
echo "• เช็คสถานะด้วยคำสั่ง: systemctl status forex-news"
echo "• ดูบันทึกการทำงาน (Log): tail -f /var/log/forex-news.log"
echo "=================================================================="
systemctl status forex-news --no-pager
