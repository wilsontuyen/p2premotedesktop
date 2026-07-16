import ctypes
from ctypes import wintypes
import win32api, win32security, win32con

def test_set_uiaccess():
    try:
        # Open current process token with TOKEN_ALL_ACCESS
        h_process = win32api.GetCurrentProcess()
        h_token = win32security.OpenProcessToken(
            h_process, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ADJUST_DEFAULT
        )
        
        # Duplicate token
        h_token_dup = win32security.DuplicateTokenEx(
            h_token,
            win32security.SecurityImpersonation,
            win32con.TOKEN_ALL_ACCESS,
            win32security.TokenPrimary
        )
        win32api.CloseHandle(h_token)
        
        # Call SetTokenInformation via ctypes
        ADVAPI32 = ctypes.WinDLL('advapi32', use_last_error=True)
        SetTokenInformation = ADVAPI32.SetTokenInformation
        SetTokenInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD
        ]
        SetTokenInformation.restype = wintypes.BOOL
        
        ui_access_val = ctypes.c_ulong(1)
        res = SetTokenInformation(
            int(h_token_dup),
            26, # TokenUIAccess
            ctypes.byref(ui_access_val),
            ctypes.sizeof(ui_access_val)
        )
        if res:
            print("SUCCESS: SetTokenInformation returned True")
            
            # Verify via GetTokenInformation
            GetTokenInformation = ADVAPI32.GetTokenInformation
            GetTokenInformation.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD)
            ]
            GetTokenInformation.restype = wintypes.BOOL
            
            uia_val = ctypes.c_ulong(0)
            ret_len = wintypes.DWORD(0)
            res_get = GetTokenInformation(
                int(h_token_dup),
                26, # TokenUIAccess
                ctypes.byref(uia_val),
                ctypes.sizeof(uia_val),
                ctypes.byref(ret_len)
            )
            if res_get:
                print(f"VERIFIED: TokenUIAccess is {uia_val.value}")
            else:
                print(f"FAIL: GetTokenInformation failed with error {ctypes.get_last_error()}")
        else:
            print(f"FAIL: SetTokenInformation failed with error {ctypes.get_last_error()}")
            
        win32api.CloseHandle(h_token_dup)
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == '__main__':
    test_set_uiaccess()
