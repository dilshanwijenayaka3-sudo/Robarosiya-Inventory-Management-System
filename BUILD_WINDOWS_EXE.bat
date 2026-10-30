@echo off
setlocal
cd /d "%~dp0"
title Build Robarosiya Inventory Windows App
where py >nul 2>&1
if errorlevel 1 goto nopy
py -m venv .buildvenv
if errorlevel 1 goto error
".buildvenv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".buildvenv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error
".buildvenv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Robarosiya Inventory" --add-data "templates;templates" --add-data "static;static" desktop_launcher.py
if errorlevel 1 goto error
echo.
echo SUCCESS: dist\Robarosiya Inventory.exe
explorer "dist"
pause
exit /b 0
:nopy
echo Python not installed. Install Python 3.10 or newer from python.org.
pause
exit /b 1
:error
echo.
echo Build failed. Please screenshot the error above.
pause
exit /b 1
