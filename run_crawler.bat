@echo off
REM Batch script to run the crawler with the correct Python environment

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Running crawler...
python main.py %*

echo.
echo To run manually:
echo   1. Activate environment: .venv\Scripts\activate.bat
echo   2. Run crawler: python main.py --dry-run