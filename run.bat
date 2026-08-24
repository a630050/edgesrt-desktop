@echo off
title Edge Live Captions Desktop
cd /d "%~dp0"

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with error code: %ERRORLEVEL%
    pause
)
