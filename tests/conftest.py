import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH for tests
ROOT_DIR = Path(__file__).resolve().parent.parent  # project root (noit_backend)
sys.path.insert(0, str(ROOT_DIR)) 