#!/bin/bash
# AI bottrade Launcher for macOS
cd "$(dirname "$0")"
echo "=================================================="
echo "   🚀 กำลังเริ่มต้นระบบ AI bottrade..."
echo "=================================================="
echo ""
echo "กำลังเปิดหน้าต่าง Dashboard ในเบราว์เซอร์ของคุณ..."
echo "URL: http://localhost:8501"
echo ""
echo "(กด Ctrl+C ในหน้าต่างนี้เมื่อต้องการหยุดการทำงาน)"
echo "=================================================="

# Open browser and run Streamlit
.venv/bin/streamlit run app.py --server.headless=false
