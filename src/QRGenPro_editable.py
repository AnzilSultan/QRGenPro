#!/usr/bin/env python3
"""
QRGenPro - Professional QR Code Generator
EDITABLE SOURCE VERSION

This is the development/editable version of QRGenPro.
Feel free to modify, customize, and extend this code.

For the production-ready version, see: QRGenPro.py
For the portable executable, see: ../dist/QRGenPro.exe

Requirements:
    pip install PySide6 Pillow qrcode[pil]

Usage:
    python QRGenPro_editable.py
"""

# ============================================================================
# NOTE: This file is identical to QRGenPro.py
# It exists as a clearly labeled copy for development purposes.
# To use this version, simply run: python QRGenPro_editable.py
# ============================================================================

# Import from the main source file
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from QRGenPro import main

if __name__ == "__main__":
    main()
