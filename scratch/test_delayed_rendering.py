import ctypes

def test():
    user32 = ctypes.windll.user32
    
    # Test without argtypes
    cf1 = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
    print(f"RegisterClipboardFormatW (no argtypes): cf1={cf1}")
    
    # Test with argtypes
    user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    cf2 = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
    print(f"RegisterClipboardFormatW (with argtypes): cf2={cf2}")

if __name__ == "__main__":
    test()
