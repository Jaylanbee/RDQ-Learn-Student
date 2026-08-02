@echo off
chcp 65001 > nul
title RDQ 學習極簡儀表板一鍵啟動器

echo ===================================================
echo 🚀 正在為您啟動 RDQ 學習極簡儀表板 (http://localhost:8000)
echo ===================================================

netstat -ano | findstr :8000 > nul
if %errorlevel% equ 0 (
    echo [✓] 儀表板伺服器已在背景執行中。
) else (
    echo [*] 正在背景啟動 RDQ 伺服器...
    start /b python "d:\2026AI_agent\RQD\server.py" > nul 2>&1
    timeout /t 2 /nobreak > nul
)

echo [✓] 正在為您開啟預設瀏覽器...
start http://localhost:8000

echo ===================================================
echo 🎉 啟動完成！您可以最小化此視窗，開始學習喔！
echo ===================================================
timeout /t 3 > nul
