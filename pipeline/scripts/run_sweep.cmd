@echo off
REM Unattended sweep for Windows Task Scheduler. Usage: run_sweep.cmd <region>
REM Task Scheduler does not inherit your shell's PATH, so name Python in full.
REM Set APPLYPILOT_HOME too if your workspace is not <repo>\workspace.
set "PY=python"
REM set "PY=C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe"
cd /d "%~dp0..\.."
if not exist "workspace\runs" mkdir "workspace\runs"
"%PY%" pipeline\ap.py sweep --region %1 >> "workspace\runs\scheduled.log" 2>&1
exit /b %ERRORLEVEL%
