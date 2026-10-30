@echo off
setlocal
cd /d "%~dp0"
title Robarosiya Hotel Inventory - Launcher
if not exist "static\style.css" goto missing
if not exist "static\logo.png" goto missing
if not exist "templates\auth.html" goto missing
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -m venv .venv
  ) else (
    where python >nul 2>&1
    if errorlevel 1 goto nopy
    python -m venv .venv
  )
  if not exist ".venv\Scripts\python.exe" goto failure
)
".venv\Scripts\python.exe" -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Installing required Flask package - Internet needed for the first run...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failure
)
echo.
echo Starting Robarosiya Hotel Inventory...
echo Keep this window open while using the application.
echo To close the app, close this window or press Ctrl+C.
".venv\Scripts\python.exe" desktop_launcher.py
if errorlevel 1 goto failure
exit /b 0
:missing
echo Project files are missing. Extract the COMPLETE ZIP first.
goto failure
:nopy
echo Python 3.10+ is required. Install Python from python.org.
goto failure
:failure
echo.
echo Could not start. Take a screenshot of the error shown above.
pause
exit /b 1
