@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0xiaogpt\.venv\Scripts\python.exe" -X utf8 "%~dp0manage_xiaogpt.py" start
pause
