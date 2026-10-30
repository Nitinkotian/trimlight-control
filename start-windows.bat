@echo off
rem Double-click to start the Trimlight app on Windows. Close this window (or press Ctrl+C) to stop it.
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python 3 is not installed. See README.md ^> Install Python.
  pause
  exit /b 1
)
%PY% webapp.py %*
if errorlevel 1 pause
