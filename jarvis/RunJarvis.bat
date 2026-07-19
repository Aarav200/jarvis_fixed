@echo off
echo Starting Jarvis systems...

:: Start Ollama in background
start "" "ollama" serve
timeout /t 3 /nobreak > nul

:: Set path and move to jarvis folder
set PATH=%PATH%;C:\Users\achaw\AppData\Local\Microsoft\WinGet\Links
cd /d "C:\Users\achaw\Downloads\jarvis_fixed\jarvis"
call venv\Scripts\activate.bat

:: Set API keys
set OPENAI_API_KEY=
set DISCORD_BOT_TOKEN=

:: Start VS Code tracker in background (separate window)
start "Jarvis VS Code Tracker" cmd /k "cd /d C:\Users\achaw\Downloads\jarvis_fixed\jarvis && venv\Scripts\activate.bat && python vscode_extension\jarvis_tracker.py"

:: Small delay then start Jarvis
timeout /t 1 /nobreak > nul
python main.py
pause
