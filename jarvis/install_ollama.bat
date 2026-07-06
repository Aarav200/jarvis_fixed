@echo off
echo Installing Ollama Python package...
cd /d "C:\Users\achaw\Downloads\jarvis_fixed\jarvis"
call venv\Scripts\activate.bat
pip install ollama
echo Done!
pause
