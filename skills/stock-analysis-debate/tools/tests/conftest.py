import sys
import os

# 让 tests 能 import tools 目录下的模块
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))
