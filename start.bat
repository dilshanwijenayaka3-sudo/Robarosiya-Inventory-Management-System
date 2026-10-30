@echo off
cd /d "%~dp0"
title Robarosiya Hotel Inventory System
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
) else (
  set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo Preparing Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto :failure
)
".venv\Scripts\python.exe" -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Installing Flask - Internet required for first setup...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failure
)
echo Opening Robarosiya Inventory...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :failure
goto :end
:failure
echo.
echo START FAILED. Please take a screenshot of this window.
pause
:end
