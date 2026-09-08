@echo off
rem ---------------------------------------------------------------------------
rem  Jianpu Converter - run from source (double-click friendly).
rem  Uses the .venv Python when present, otherwise the system python.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" app_gui.py %*
if errorlevel 1 pause
