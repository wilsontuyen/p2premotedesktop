import win32clipboard, time

win32clipboard.OpenClipboard()
win32clipboard.EmptyClipboard()
win32clipboard.SetClipboardData(15, None)
win32clipboard.CloseClipboard()
print("Clipboard set to delayed. Go to explorer and press Ctrl+V.")
time.sleep(60)
