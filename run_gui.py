#!/usr/bin/env python3
"""
Launcher script for CAN Analyzer GUI
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from can_gui import main

if __name__ == '__main__':
    main()
