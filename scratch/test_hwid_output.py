import sys
import os

# Append current directory to path
sys.path.append(os.getcwd())

from app import get_hwid

id_clean, id_formatted = get_hwid()
print("New Clean HWID:", id_clean)
print("New Formatted HWID:", id_formatted)
