import ctypes

def test_leak():
    for i in range(10):
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x02000000)
        print(f"hdesk: {hdesk}")
        if hdesk:
            result = ctypes.windll.user32.SetThreadDesktop(hdesk)
            print(f"SetThreadDesktop: {result}")
            res_close = ctypes.windll.user32.CloseDesktop(hdesk)
            err = ctypes.windll.kernel32.GetLastError() if res_close == 0 else 0
            print(f"CloseDesktop: {res_close}, Error: {err}")

test_leak()
