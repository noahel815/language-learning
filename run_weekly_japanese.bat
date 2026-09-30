@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if "%~1"=="" (
  echo Drag a reviewed content JSON onto this file, or pass its path as argument.
  echo No sample content will be generated automatically.
  pause
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 generator\generate_weekly_japanese.py --content "%~1"
) else (
  where python >nul 2>nul
  if not errorlevel 1 (
    python generator\generate_weekly_japanese.py --content "%~1"
  ) else (
    echo Python 3 was not found. Install Python 3, then run this file again.
    pause
    exit /b 1
  )
)
if errorlevel 1 (
  echo.
  echo Weekly Japanese generation FAILED. Please keep this window and review the error above.
  pause
  exit /b 1
)
echo.
echo Weekly Japanese generation and QA PASSED.
pause
