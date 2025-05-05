#!/usr/bin/env python
"""
Simple script to verify the Poetry virtual environment is working correctly.
"""
import sys
import os
import subprocess

def check_environment():
    # Print Python version and path
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    
    # Check if we're in a virtual environment
    in_venv = sys.prefix != sys.base_prefix
    print(f"In virtual environment: {in_venv}")
    
    # Check if important packages are available
    try:
        import fastapi
        print(f"FastAPI version: {fastapi.__version__}")
    except ImportError:
        print("FastAPI not found!")
    
    try:
        import uvicorn
        print(f"Uvicorn version: {uvicorn.__version__}")
    except ImportError:
        print("Uvicorn not found!")

if __name__ == "__main__":
    check_environment() 