import ctypes

def test_leak2():
    last_hdesk = None
    for i in range(10):
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x02000000)
        print(f"hdesk: {hdesk}")
        if hdesk:
            result = ctypes.windll.user32.SetThreadDesktop(hdesk)
            print(f"SetThreadDesktop: {result}")
            if last_hdesk:
                res_close = ctypes.windll.user32.CloseDesktop(last_hdesk)
                err = ctypes.windll.kernel32.GetLastError() if res_close == 0 else 0
                print(f"CloseDesktop old: {res_close}, Error: {err}")
            last_hdesk = hdesk

test_leak2()
