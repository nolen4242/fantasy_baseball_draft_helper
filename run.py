#!/usr/bin/env python3
"""Simple script to run the Flask application."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.app import app

if __name__ == '__main__':
    print("=" * 60)
    print("Fantasy Baseball Draft Helper")
    print("=" * 60)
    print("\nStarting server on http://localhost:5001")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, port=5001)

