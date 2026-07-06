@echo off
title Jarvis Voice Assistant
cd /d "%~dp0"

echo ============================================
echo           JARVIS Voice Assistant
echo ============================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Python not found. Install Python 3.10+ from python.org
        pause
        exit /b 1
    )
    echo [SETUP] Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Dependency installation failed. See errors above.
        pause
        exit /b 1
    )
    echo [SETUP] Setup complete!
    echo.
)

REM Check for API key
if "%OPENAI_API_KEY%"=="" (
    echo WARNING: OPENAI_API_KEY not set.
    echo Jarvis will run in offline fallback mode.
    echo To set it, run:  set OPENAI_API_KEY=sk-your-key-here
    echo.
)

echo Starting Jarvis...
echo Say "Hey Jarvis" to activate.
echo Press Ctrl+C to stop.
echo.

venv\Scripts\python.exe jarvis\main.py
pause
