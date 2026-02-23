@echo off
chcp 65001 >nul
echo.
echo  🎵 Music Tab Finder - AI 音樂轉譜助手
echo  ════════════════════════════════════════
echo.
echo  正在啟動服務...
echo.

cd /d "%~dp0backend"
.venv\Scripts\python.exe main.py

pause
