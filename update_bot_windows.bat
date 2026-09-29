@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   AI bottrade - Auto Update Tool (Windows VPS)
echo ========================================================
echo.
echo [*] กำลังดึงโค้ดอัปเดตล่าสุดจาก GitHub...
git pull
if %errorlevel% neq 0 (
    echo.
    echo [!] หากเครื่องนี้ยังไม่ได้ติดตั้ง Git หรือพบข้อผิดพลาด
    echo [!] คุณสามารถ Copy โฟลเดอร์ "src" จากเครื่อง Mac มาวางทับได้โดยตรงครับ
) else (
    echo.
    echo [OK] อัปเดตโค้ดระบบใหม่ล่าสุดสำเร็จเรียบร้อยแล้ว!
)
echo.
echo กดปุ่มใดๆ เพื่อปิดหน้าต่างนี้...
pause >nul
