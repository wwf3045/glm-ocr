@echo off
setlocal
cd /d "%~dp0"
set "DIST_DIR=%~dp0dist\OCRDuplicateReviewer_compact"
set "ZIP_PATH=%~dp0dist\OCRDuplicateReviewer_compact.zip"
"D:\anaconda3\Scripts\pyinstaller.exe" --noconfirm --clean duplicate_image_reviewer_app.spec
if errorlevel 1 exit /b 1
"D:\anaconda3\python.exe" "%~dp0package_portable_zip.py" "%DIST_DIR%" "%ZIP_PATH%"
