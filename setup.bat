@echo off
REM Quick setup script for CAN Bus Analyzer (Windows)
REM Run this to set up virtual environment and install dependencies

echo CAN Bus Analyzer - Setup Script
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.7 or higher.
    pause
    exit /b 1
)

python --version
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Verify installation
echo.
echo Verifying installation...
python -c "import can, matplotlib, numpy, pandas, tkinter; print('✓ All libraries installed successfully!')"

if errorlevel 1 (
    echo.
    echo Warning: Some libraries may not be installed correctly
    echo Try running: pip install -r requirements.txt
) else (
    echo.
    echo ================================
    echo Setup complete!
    echo.
    echo To use the application:
    echo   1. Activate virtual environment: venv\Scripts\activate
    echo   2. Run GUI: python can_gui.py
    echo.
    echo To deactivate when done: deactivate
)

pause
