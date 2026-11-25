@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt || goto :fail
py build.py || goto :fail
start "" http://localhost:8000/
py -m http.server 8000 --bind 127.0.0.1 --directory dist
exit /b
:fail
echo Build failed. See errors above.
pause
exit /b 1
