@echo off
setlocal

set "LAUNCHER_EXE=%~dp0OCRDuplicateReviewerLauncher.exe"
if exist "%LAUNCHER_EXE%" (
  start "" "%LAUNCHER_EXE%"
  exit /b 0
)

set "APP_DIR=%~dp0dist\OCRDuplicateReviewer_compact"
if not exist "%APP_DIR%\OCRDuplicateReviewer.exe" set "APP_DIR=%~dp0dist\OCRDuplicateReviewer"
set "APP_EXE=%APP_DIR%\OCRDuplicateReviewer.exe"

if not exist "%APP_EXE%" (
  echo OCRDuplicateReviewer launcher not found.
  echo Expected either:
  echo   %LAUNCHER_EXE%
  echo   %APP_EXE%
  pause
  exit /b 1
)

cd /d "%APP_DIR%"
start "" "%APP_EXE%"
