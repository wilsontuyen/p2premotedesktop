WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3

# ─Éß╗ïnh ngh─⌐a c├íc kiß╗âu dß╗» liß╗çu t╞░╞íng th├¡ch 64-bit ─æß╗â tr├ính lß╗ùi OverflowError tr├¬n Windows 64-bit
WPARAM_64 = ctypes.c_size_t
LPARAM_64 = ctypes.c_ssize_t
LRESULT_64 = ctypes.c_ssize_t

try:
    WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64)
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", ctypes.c_void_p)]
except:
    pass

# Khß╗ƒi tß║ío tr╞░ß╗¢c th├┤ng sß╗æ kiß╗âu dß╗» liß╗çu cß╗ºa DefWindowProcW ─æß╗â tr├ính lß╗ùi trong qu├í tr├¼nh tß║ío cß╗¡a sß╗ò
try:
    ctypes.windll.user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64]
    ctypes.windll.user32.DefWindowProcW.restype = LRESULT_64
except:
    pass

class ClipboardEventListener:
    def __init__(self, callback, manager=None):
        self.callback = callback
        self.manager = manager
        self.hwnd = None
        self.mouse_hook = None
        self.mouse_hook_callback = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _mouse_hook_proc(self, nCode, wParam, lParam):
        if nCode >= 0:
            # WM_RBUTTONDOWN = 0x0204, WM_RBUTTONUP = 0x0205, WM_NCRBUTTONDOWN = 0x00A4, WM_NCRBUTTONUP = 0x00A5
            if wParam in (0x0204, 0x0205, 0x00A4, 0x00A5):
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
                    log_debug(f"[MouseHook] Ph├ít hiß╗çn click chuß╗Öt phß║úi l├║c: {self.manager.last_rbutton_time}")
            # WM_LBUTTONDOWN = 0x0201, WM_LBUTTONUP = 0x0202, WM_NCLBUTTONDOWN = 0x00A1, WM_NCLBUTTONUP = 0x00A2
            elif wParam in (0x0201, 0x0202, 0x00A1, 0x00A2):
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhß║¡n WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhß║¡n WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0
        elif msg == WM_DESTROYCLIPBOARD:
            log_debug(f"[WndProc] Nhß║¡n WM_DESTROYCLIPBOARD")
            if self.manager:
                self.manager.lost_ownership()
            return 0
        elif msg == WM_SETUP_DELAYED_RENDERING:
            log_debug(f"[WndProc] Nhß║¡n WM_SETUP_DELAYED_RENDERING. ─Éang tiß║┐n h├ánh thiß║┐t lß║¡p delayed rendering...")
            if self.manager:
                self.manager._execute_setup_delayed_rendering()
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0

    def _run(self):
        try:
            log_debug("[Listener] Bß║»t ─æß║ºu thread ─æ─âng k├╜ Clipboard listener.")
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # ─Éß╗ïnh ngh─⌐a types cho GetModuleHandleW tr╞░ß╗¢c khi gß╗ìi
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            h_mod = kernel32.GetModuleHandleW(None)
            
            # ─Éß╗ïnh ngh─⌐a types cho CallNextHookEx ─æß╗â tr├ính lß╗ùi OverflowError tr├¬n 64-bit Windows
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM_64, LPARAM_64]
            user32.CallNextHookEx.restype = LRESULT_64
            
            # ─É─âng k├╜ Low-level Mouse Hook ─æß╗â theo d├╡i chuß╗Öt phß║úi to├án hß╗ç thß╗æng
            try:
                HOOKPROC = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_int, WPARAM_64, LPARAM_64)
                self.mouse_hook_callback = HOOKPROC(self._mouse_hook_proc)
                user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD]
                user32.SetWindowsHookExW.restype = wintypes.HANDLE
                
                self.mouse_hook = user32.SetWindowsHookExW(
                    14, # WH_MOUSE_LL = 14
                    self.mouse_hook_callback,
                    h_mod,
                    0
                )
                log_debug(f"[Listener] ─É├ú ─æ─âng k├╜ Low-level Mouse Hook th├ánh c├┤ng: {self.mouse_hook}")
            except Exception as e:
                log_debug(f"[Listener] Lß╗ùi ─æ─âng k├╜ Mouse Hook: {e}")

            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            ]
            user32.CreateWindowExW.restype = ctypes.c_void_p
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p

            wndproc = WNDPROCTYPE(self._wndproc)
            self.wndproc_ref = wndproc  # Giß╗» reference ─æß╗â tr├ính bß╗ï garbage collected
            wndclass = WNDCLASSEX()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
            wndclass.lpfnWndProc = wndproc
            wndclass.lpszClassName = "HiddenClipboardListener"
            wndclass.hInstance = kernel32.GetModuleHandleW(None)
            
            reg_res = user32.RegisterClassExW(ctypes.byref(wndclass))
            log_debug(f"[Listener] RegisterClassExW trß║ú vß╗ü: {reg_res}")
            
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE), None, wndclass.hInstance, None)
            log_debug(f"[Listener] CreateWindowExW trß║ú vß╗ü HWND: {self.hwnd}")
            
            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trß║ú vß╗ü: {add_res}")
            
            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                
            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))
            user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)
        except Exception as e:
            print("[ClipboardEvent] Lß╗ùi Listener:", e)

    def stop(self):
        self.running = False
        if self.mouse_hook:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self.mouse_hook)
                log_debug("[Listener] ─É├ú gß╗í bß╗Å Low-level Mouse Hook.")
            except Exception as e:
                log_debug(f"[Listener] Lß╗ùi gß╗í bß╗Å Mouse Hook: {e}")
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass
