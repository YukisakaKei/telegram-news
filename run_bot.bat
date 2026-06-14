@echo off
chcp 65001 >nul
cd /d "D:\Agent\telegram-news"
python main.py >> logs\bot_%date:~0,4%%date:~5,2%%date:~8,2%%time:~0,2%%time:~3,2%.log 2>&1
