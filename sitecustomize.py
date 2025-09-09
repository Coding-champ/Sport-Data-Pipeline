# Automatically add the project's src/ directory to sys.path for local execution of scripts
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if os.path.isdir(SRC_PATH) and SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
