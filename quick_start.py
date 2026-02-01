#!/usr/bin/env python3
"""
CVSE Quick Start
"""

import sys

def main():
    print("CVSE Quick Start")
    print("Dependencies: flask flask-cors pycapnp")
    print("Install: pip install flask flask-cors pycapnp")
    print("")
    
    try:
        from server import app
        app.run(host='0.0.0.0', port=5123, debug=False)
    except ImportError as e:
        print(f"Import failed: {e}")
        print("Please install dependencies or check CVSE submodule")
    except KeyboardInterrupt:
        print("\nServer stopped")

if __name__ == "__main__":
    main()