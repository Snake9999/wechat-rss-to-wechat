@echo off
set SCRIPT_DIR=%~dp0
if exist "%SystemRoot%\py.exe" (
  py -3 "%SCRIPT_DIR%run_pipeline.py" %*
) else (
  python "%SCRIPT_DIR%run_pipeline.py" %*
)
