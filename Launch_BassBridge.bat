@echo off
title BassBridge Launcher
cd /d "%~dp0"
if exist "dist\BassBridge\BassBridge.exe" (
    echo Launching BassBridge Standalone Application...
    start "" "dist\BassBridge\BassBridge.exe"
    exit /b 0
) else (
    echo Starting BassBridge via Python...
    python main.py
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while launching BassBridge.
    pause
)
