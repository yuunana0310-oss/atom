@echo off
title AGENS_ULTIMATE_LAUNCHER
color 0b

echo [SYSTEM] Ensuring clean environment...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    if NOT "%%a"=="0" taskkill /f /pid %%a > nul 2>&1
)

echo [1/2] Starting Server on Port 8000...

:: Ensure we are in the right directory
cd /d "%~dp0"

:: Start the custom API server in a separate process
start "AGENS_SERVER" /min python api_server.py

:: Wait for server to start
echo [2/2] Opening Dashboard...
ping 127.0.0.1 -n 5 > nul

:: Open Browser
start http://localhost:8000

echo.
echo ==========================================
echo  DONE: Dashboard is loading in browser.
echo  If the page is blank, check the server window.
echo ==========================================
echo.

:: Keep window open even if errors occur above
cmd /k
