@echo off
cd /d "D:\Agent\telegram-news"
python main.py >> logs\bot_%date:~0,4%%date:~5,2%%date:~8,2%.log 2>&1
