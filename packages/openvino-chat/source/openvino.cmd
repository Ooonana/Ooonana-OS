@echo off
setlocal EnableDelayedExpansion
set "PROJECT=%~dp0"
if "%PROJECT:~-1%"=="\" set "PROJECT=%PROJECT:~0,-1%"
set "PY=%OPENVINO_PYTHON%"
if not defined PY if exist "%PROJECT%\.venv\Scripts\python.exe" set "PY=%PROJECT%\.venv\Scripts\python.exe"
if not defined PY set "PY=python"
if not defined OPENVINO_HOME set "OPENVINO_HOME=%USERPROFILE%\.openvino"

set "PYTHONPATH=%PROJECT%\src;%PYTHONPATH%"
"%PY%" -m openvino_chat %*
exit /b !ERRORLEVEL!
