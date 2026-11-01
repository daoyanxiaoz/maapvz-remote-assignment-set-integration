@echo off
rem ============================================================
rem  MAAPVZ site preview launcher (read-only)
rem  ASCII-only on purpose: cmd.exe parses .bat with the OEM code
rem  page, so UTF-8 Chinese here would break the script.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title MAAPVZ site preview

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

%PY% -X utf8 "tools\dev_server.py" --preview %*
echo.
echo  Preview stopped. You can close this window.
pause
