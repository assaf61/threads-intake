@echo off
cd /d "%~dp0"
echo threads-intake local server: http://localhost:8848/
python -m http.server 8848
