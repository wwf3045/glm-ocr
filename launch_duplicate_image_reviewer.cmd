@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=D:\anaconda3\python.exe"

if "%~1"=="" (
  set "TARGET_ROOT=F:\中间文件库\数学\规划与优化\最优化理论"
) else (
  set "TARGET_ROOT=%~1"
)

cd /d "%SCRIPT_DIR%"
"%PYTHON_EXE%" "%SCRIPT_DIR%duplicate_image_reviewer.py" --root "%TARGET_ROOT%"

