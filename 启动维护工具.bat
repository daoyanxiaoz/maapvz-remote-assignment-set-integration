@echo off
rem ============================================================
rem  MAAPVZ job-set tool launcher
rem  This file is ASCII-only on purpose: cmd.exe parses .bat with
rem  the OEM code page, so UTF-8 Chinese here would break the script.
rem  All Chinese messages come from tools\dev_server.py.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title MAAPVZ job-set tool

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  [x] Python 3 not found.
  echo      Install from https://www.python.org/downloads/
  echo      and tick "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)

%PY% -X utf8 "tools\dev_server.py" %*
echo.
echo  Tool stopped. You can close this window.
pause
