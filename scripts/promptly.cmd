@echo off
rem `promptly` launcher for native Windows (cmd.exe / PowerShell).
rem
rem Windows won't execute a bare Python file by name the way a POSIX shebang
rem does, so this batch file is what goes on PATH instead of a symlink to
rem scripts\promptly. It just finds the right interpreter and hands off to
rem that file, which does everything else (venv re-exec, argument parsing).
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%..\backend\venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" "%SCRIPT_DIR%promptly" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if errorlevel 1 (
    echo promptly: python not found on PATH. Install Python 3.10+ from python.org and re-run setup.ps1
    exit /b 1
)
python "%SCRIPT_DIR%promptly" %*
exit /b %ERRORLEVEL%
