@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage_api.ps1" %*
exit /b %ERRORLEVEL%
