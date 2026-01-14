#!/bin/bash
# Quick setup script for CAN Bus Analyzer
# Run this to set up virtual environment and install dependencies

echo "CAN Bus Analyzer - Setup Script"
echo "================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.7 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Verify installation
echo ""
echo "Verifying installation..."
python -c "import can, matplotlib, numpy, pandas, tkinter; print('✓ All libraries installed successfully!')"

if [ $? -eq 0 ]; then
    echo ""
    echo "================================"
    echo "Setup complete!"
    echo ""
    echo "To use the application:"
    echo "  1. Activate virtual environment: source venv/bin/activate"
    echo "  2. Run GUI: python can_gui.py"
    echo ""
    echo "To deactivate when done: deactivate"
else
    echo ""
    echo "Warning: Some libraries may not be installed correctly"
    echo "Try running: pip install -r requirements.txt"
fi
