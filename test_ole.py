import win32com.server.policy
import pythoncom
import win32con
import time

# Try to see if OleSetClipboard is available
try:
    print("Has OleSetClipboard?", hasattr(pythoncom, 'OleSetClipboard'))
except Exception as e:
    print(e)
