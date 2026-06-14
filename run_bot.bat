@echo off
chcp 65001 >nul
cd /d "D:\Agent\telegram-news"
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%i
python main.py >> logs\bot_%TIMESTAMP%.log 2>&1
