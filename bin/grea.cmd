@echo off
setlocal
if not exist "%~dp0..\.venv\Scripts\python.exe" (
  echo grea runtime missing. Run uv sync --project "%~dp0.." --frozen 1>&2
  exit /b 2
)
"%~dp0..\.venv\Scripts\python.exe" "%~dp0..\launch.py" %*
exit /b %errorlevel%
