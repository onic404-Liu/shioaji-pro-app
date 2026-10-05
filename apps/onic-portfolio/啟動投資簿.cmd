@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ONIC_PYTHON=%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
if not exist "%ONIC_PYTHON%" (
  echo Installed Python 3.11 not found. Please read README.md.
  pause
  exit /b 1
)
"%ONIC_PYTHON%" -I -X utf8 "launch_web.py" %*
pause
