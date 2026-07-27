import pygame
import threading
import time
import ctypes
from ctypes import wintypes
import sys
import os
import json
import io
import struct
try:
    from PIL import Image
except ImportError:
    pass

from core.config import *
from network.socket_utils import socket_passwords
from PIL import ImageTk
from gui.components import ProgressDialog
from utils.clipboard_api import get_clipboard_text
import socket
from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode

from core.i18n import _
from utils.logger import log_debug, log_activity
from network.socket_utils import send_msg, recv_msg
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_move, send_input_mouse_scroll

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

file_manager_callback = None

# Shared client variables
client_latest_frame = None
client_last_recv_time = 0
client_frame_lock = threading.Lock()
client_running = True
client_is_domain = False
client_is_locked = False
client_switching_desktop_countdown = 0
client_host_resolution = None
client_host_did_shutdown = False
client_host_computer_name_override = None

# Client Screen Receiver Thread
def client_receiver_thread(sock, password):
    global client_latest_frame, client_running, client_switching_desktop_countdown, client_is_domain, client_is_locked, client_host_did_shutdown
    client_pending_bbox = None
    while client_running:
        try:
            msg = recv_msg(sock, password)
            if not msg:
                print("[Client] Server closed connection.")
                # Nếu host là Linux/Ubuntu (không phải Windows), đóng luôn viewer
                # vì mất kết nối đột ngột trên Linux thường do shutdown/restart
                host_os = globals().get('client_host_os_release', '10')
                is_host_windows = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in str(host_os)
                if not is_host_windows:
                    print("[Client] Non-Windows host connection closed. Treating as host shutdown.")
                    client_host_did_shutdown = True
                client_running = False
                break
            
            # [FIX] Decrypt failure trả về b'' thay vì None — log rõ ràng thay vì fail lặng lẽ
            if msg == b'':
                print("[Client] WARNING: Received empty message (decryption may have failed). Skipping.")
                continue
                
            global client_last_recv_time
            client_last_recv_time = time.time()
                
            if msg.startswith(b'{'):
                try:
                    event = json.loads(msg.decode('utf-8'))
                    evt_type = event.get("type", "")
                    if evt_type == "pong":
                        continue
                    elif evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text", "clipboard_image"):
                        if clipboard_sync_manager:
                            clipboard_sync_manager.handle_received_packet(event)
                        continue
                    elif evt_type == "domain_status":
                        client_is_domain = event.get("is_domain", False)
                        client_is_locked = event.get("is_locked", False)
                        reason = event.get("reason", "No reason provided")
                        try:
                            with open("domain_debug.log", "a", encoding="utf-8") as df:
                                df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client received domain_status: is_domain={client_is_domain}, is_locked={client_is_locked}, reason={reason}\n")
                        except:
                            pass
                        continue
                    elif evt_type == "switching_desktop":
                        if client_switching_desktop_countdown <= 0:
                            client_switching_desktop_countdown = 10
                        continue
                    elif evt_type == "host_shutdown":
                        print("[Client] Received host_shutdown. Exiting viewer immediately.")
                        client_host_did_shutdown = True
                        import pygame
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                        continue
                    elif evt_type == "resolution_change":
                        new_w = event.get("w")
                        new_h = event.get("h")
                        if new_w and new_h:
                            global client_host_resolution
                            client_host_resolution = (new_w, new_h)
                        continue
                    elif evt_type == "partial_frame":
                        client_pending_bbox = event.get("bbox")
                        continue
                    elif evt_type in ("list_dir_result", "delete_item_result", "rename_item_result", "create_folder_result", "open_file_result", "read_text_file_result", "write_text_file_result", "get_properties_result", "batch_start", "file_start", "file_chunk", "file_end", "batch_end"):
                        if evt_type == "read_text_file_result" and event.get("path") == "/sys/block/mmcblk0/device/serial":
                            if event.get("success"):
                                serial = event.get("content", "").strip()
                                if serial.startswith("0x"):
                                    serial = serial[2:]
                                if serial:
                                    comp = f"MC-Android {serial}"
                                    global client_host_computer_name_override
                                    client_host_computer_name_override = comp
                            continue
                            
                        global file_manager_callback
                        if file_manager_callback:
                            file_manager_callback(event)
                        continue
                except Exception as je:
                    print(f"[Client] Lỗi giải mã gói tin JSON: {je}")
                    pass
                continue


            import io
            try:
                pil_img = Image.open(io.BytesIO(msg))
                pil_img.load()  # Force decode in receiver thread
                with client_frame_lock:
                    if client_pending_bbox is not None:
                        if client_latest_frame is not None:
                            temp = client_latest_frame.copy()
                            temp.paste(pil_img, (client_pending_bbox[0], client_pending_bbox[1]))
                            client_latest_frame = temp
                        client_pending_bbox = None
                    else:
                        client_latest_frame = pil_img
                client_switching_desktop_countdown = 0
            except Exception as ie:
                with open("client_error.log", "a", encoding="utf-8") as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S') + _(" - [Client] Lỗi giải mã ảnh Pillow: ") + str(ie) + "\n")
        except Exception as e:
            with open("client_error.log", "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - [Client] Receiver Error: {e}\n")
            # Nếu host là Linux/Ubuntu, socket error thường do shutdown/restart
            host_os = globals().get('client_host_os_release', '10')
            is_host_windows = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in str(host_os)
            if not is_host_windows:
                print(f"[Client] Non-Windows host socket error: {e}. Treating as host shutdown.")
                client_host_did_shutdown = True
            client_running = False
            break

# Client keyboard hook helper functions
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

_keyboard_hook = None
_keyboard_hook_id = None

def install_keyboard_hook(hwnd, send_event_fn):
    import sys
    if sys.platform != "win32":
        return
    global _keyboard_hook, _keyboard_hook_id
    
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    LRESULT = ctypes.c_int64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_int32
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_size_t
    
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
    
    def hook_proc(nCode, wParam, lParam):
        if nCode >= 0:
            try:
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                active_hwnd = user32.GetForegroundWindow()
                if hwnd and active_hwnd == hwnd:
                    kbd = KBDLLHOOKSTRUCT.from_address(lParam)
                    vkCode = kbd.vkCode
                    
                    is_win_key = (vkCode == 0x5B or vkCode == 0x5C)
                    is_menu_key = (vkCode == 0x5D)  # VK_APPS - phím Menu/Application (right-click keyboard key)
                    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                    user32.GetAsyncKeyState.restype = ctypes.c_short
                    is_ctrl_esc = (vkCode == 0x1B and (user32.GetAsyncKeyState(0x11) & 0x8000))
                    is_alt_f4 = (vkCode == 0x73 and (kbd.flags & 0x20))
                    
                    if is_win_key or is_ctrl_esc or is_menu_key or is_alt_f4:
                        pressed = (wParam == 0x0100 or wParam == 0x0104) # WM_KEYDOWN or WM_SYSKEYDOWN
                        
                        if is_win_key:
                            key_name = 'left windows' if vkCode == 0x5B else 'right windows'
                        elif is_menu_key:
                            key_name = 'menu'
                        elif is_alt_f4:
                            key_name = 'f4'
                        else:
                            key_name = 'escape'
                            
                        send_event_fn({
                            "type": "key_event",
                            "key": key_name,
                            "pressed": pressed
                        })
                        
                        return 1
            except Exception:
                pass
                
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM, LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        return user32.CallNextHookEx(None, nCode, wParam, lParam)
        
    _keyboard_hook = HOOKPROC(hook_proc)
    
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    h_mod = kernel32.GetModuleHandleW(None)
    
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE
    
    _keyboard_hook_id = user32.SetWindowsHookExW(13, _keyboard_hook, h_mod, 0)
    if not _keyboard_hook_id:
        print(f"[Client] Hook keyboard failed. Error: {ctypes.GetLastError()}")
    else:
        print(f"[Client] Keyboard hook installed successfully: {_keyboard_hook_id}")

def uninstall_keyboard_hook():
    import sys
    if sys.platform != "win32":
        return
    global _keyboard_hook_id
    if _keyboard_hook_id:
        user32 = ctypes.windll.user32
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.UnhookWindowsHookEx(_keyboard_hook_id)
        _keyboard_hook_id = None
        print("[Client] Keyboard hook uninstalled.")

# Client Main View Pygame Loop
def run_client_viewer_loop(sock, host_w, host_h, computer_name="", is_domain=False, partner_id="", reconnect_queue=None, partner_pass="", is_android=False, os_release=""):
    global client_switching_desktop_countdown, client_host_computer_name_override
    
    try: log_activity(_("Bắt đầu điều khiển ID ") + str(partner_id) + " (" + str(computer_name) + ")")
    except: pass
    
    # [FIX] Trong Windows, multiprocessing.Process khởi tạo tiến trình con mới hoàn toàn.
    # Từ điển socket_passwords toàn cục bị trống, dẫn đến encrypt_payload mặc định dùng APP_KEY,
    # gây ra lỗi InvalidTag khi Host giải mã dữ liệu clipboard/file.
    if partner_pass:
        socket_passwords[sock] = partner_pass
        
    globals()['client_host_os_release'] = os_release if os_release else "10"
    
    try:
        pygame_theme = "dark"
        try:
            import json, os
            with open("window_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                pygame_theme = cfg.get("theme", "dark")
                
                # Cấu hình lại ngôn ngữ cho tiến trình mới
                from core.i18n import load_language
                load_language(cfg.get("language", "vi"))
        except:
            pass

        outer_running = True
        
        # Initialize Pygame once outside the loop
        import os
        os.environ['SDL_MOUSE_FOCUS_CLICKTHROUGH'] = '1'
        os.environ['SDL_RENDER_DRIVER'] = 'hardware'
        pygame.init()
        pygame.key.set_repeat(500, 50)
        
        info = pygame.display.Info()
        client_max_w = info.current_w - 100
        client_max_h = info.current_h - 100
        
        ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
        
        # [Tùy chỉnh Android] Thu nhỏ màn hình mặc định nếu là thiết bị di động (màn hình dọc)
        if host_h > host_w:
            max_portrait_height = min(900, client_max_h) # Giới hạn chiều cao tối đa khoảng 900px
            if host_h * ratio > max_portrait_height:
                ratio = max_portrait_height / host_h
                
        window_w = int(host_w * ratio)
        window_h = int(host_h * ratio)
        
        window_w = max(100, min(window_w, 3840))
        window_h = max(100, min(window_h, 2160))
        
        try:
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        except Exception as e:
            print(f"[Client] Hardware rendering failed ({e}). Falling back to software rendering.")
            os.environ['SDL_RENDER_DRIVER'] = 'software'
            pygame.display.quit()
            pygame.display.init()
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        
        hwnd = None
        try: hwnd = pygame.display.get_wm_info().get("window")
        except: pass
        if hwnd and clipboard_sync_manager:
            clipboard_sync_manager.pygame_hwnd = hwnd
        import tempfile
        blink_file = ""
        if partner_id:
            blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
            if os.path.exists(blink_file):
                try: os.remove(blink_file)
                except: pass
                
        if computer_name:
            pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=computer_name))
        else:
            pygame.display.set_caption(_("P2P Remote Desktop Viewer"))
            
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception as e:
            print(f"[App] Lỗi thiết lập icon cửa sổ pygame: {e}")
            
        import core.i18n
        lang = getattr(core.i18n, '_current_lang', 'en')
        if lang == 'jp':
            font_names = "Meiryo, Yu Gothic, MS Gothic, Segoe UI, Arial"
        elif lang == 'kr':
            font_names = "Malgun Gothic, Gulim, Segoe UI, Arial"
        elif lang in ['cn', 'tw']:
            font_names = "Microsoft YaHei, Microsoft JhengHei, SimHei, Segoe UI, Arial"
        else:
            font_names = "Segoe UI, Arial"
            
        try: btn_font = pygame.font.SysFont(font_names, 12, bold=True)
        except:
            try: btn_font = pygame.font.SysFont("Arial", 12, bold=True)
            except: btn_font = pygame.font.Font(None, 20)
            
        clock = pygame.time.Clock()
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        
        while outer_running:
            exit_due_to_disconnect = True
            global client_latest_frame, client_running, client_is_domain, client_is_locked, client_last_recv_time, client_host_did_shutdown
            client_latest_frame = None
            client_last_recv_time = time.time()
            client_running = True
            client_host_did_shutdown = False
            client_is_domain = is_domain
            
            try:
                # Check if domain was already queried and reason passed in handshake (or check local log)
                with open("domain_debug.log", "a", encoding="utf-8") as df:
                    df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client viewer started: computer_name={computer_name}, is_domain={is_domain}, partner_id={partner_id}\n")
            except:
                pass
                
            import tkinter as tk
            hidden_root = tk.Tk()
            hidden_root.attributes('-alpha', 0.0)
            try:
                icon_path = os.path.join(app_dir, "app_icon.png")
                if os.path.exists(icon_path):
                    try:
                        hidden_icon = tk.PhotoImage(file=icon_path)
                    except Exception:
                        hidden_icon = ImageTk.PhotoImage(Image.open(icon_path))
                    hidden_root.iconphoto(True, hidden_icon)
                    hidden_root._hidden_icon_ref = hidden_icon
            except Exception:
                pass
            hidden_root.withdraw()
            if clipboard_sync_manager:
                clipboard_sync_manager.register_app(hidden_root)
            
            # Start receiver thread
            t = threading.Thread(target=client_receiver_thread, args=(sock, partner_pass), daemon=True)
            t.start()
            
            # Gắn kết socket vào trình quản lý Event Listener của Clipboard
            if clipboard_sync_manager:
                clipboard_sync_manager.add_socket(sock)
            # We moved pygame init outside
            
            import queue
            import collections
            # Queue riêng cho sự kiện quan trọng (click, key, scroll) - KHÔNG bao giờ bị drop
            critical_queue = queue.Queue()
            # Buffer mouse_move: chỉ giữ vị trí mới nhất, tránh làm đầy queue và mất click
            _mouse_move_buf = {}
            _mouse_move_lock = threading.Lock()
            _mouse_move_has_new = threading.Event()
            
            def event_sender_thread():
                last_ping_time = time.time()
                while client_running:
                    try:
                        now = time.time()
                        if now - last_ping_time >= 3.0:
                            send_msg(sock, json.dumps({"type": "ping"}).encode('utf-8'), partner_pass)
                            last_ping_time = now

                        # Ưu tiên gửi sự kiện quan trọng (click/key/scroll) trước
                        try:
                            event_dict = critical_queue.get_nowait()
                            send_msg(sock, json.dumps(event_dict).encode('utf-8'), partner_pass)
                            continue
                        except queue.Empty:
                            pass
                        # Nếu không có sự kiện quan trọng, gửi mouse_move mới nhất nếu có
                        if _mouse_move_has_new.wait(timeout=0.05):
                            with _mouse_move_lock:
                                move = _mouse_move_buf.get("latest")
                                _mouse_move_has_new.clear()
                            if move:
                                send_msg(sock, json.dumps(move).encode('utf-8'), partner_pass)
                    except Exception:
                        break
                        
            threading.Thread(target=event_sender_thread, daemon=True).start()
            
            # Khởi tạo kích thước viewer ban đầu cho Host biết
            def send_event(event_dict):
                try:
                    evt_type = event_dict.get("type")
                    if evt_type == "mouse_move":
                        # Chỉ giữ vị trí mới nhất, bỏ các vị trí cũ để không làm block click
                        with _mouse_move_lock:
                            _mouse_move_buf["latest"] = event_dict
                        _mouse_move_has_new.set()
                    else:
                        # Click, key, scroll: KHÔNG bao giờ drop, đưa thẳng vào critical_queue
                        critical_queue.put(event_dict)
                except Exception:
                    pass
                    
            # Install keyboard hook to intercept Windows keys and Ctrl+Esc
            if hwnd:
                install_keyboard_hook(hwnd, send_event)
                
            if is_android:
                send_event({"type": "request_read_text_file", "path": "/sys/block/mmcblk0/device/serial"})
                
            send_event({"type": "check_domain"})
            send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
            
            frame_counter = 0
            blink_frames_remaining = 0
            active_unicode_map = {}
            was_switching = False
            switching_last_tick = 0
            switching_start_tick = 0
            drag_start_pos = None
            drag_start_time = 0
            drag_path = []
            
            last_seen_override = None
            
            while client_running:
                if client_host_computer_name_override != last_seen_override:
                    last_seen_override = client_host_computer_name_override
                    if last_seen_override:
                        pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=last_seen_override))

                frame_counter += 1
                # Check for blink signal file periodically
                if blink_file and frame_counter % 15 == 0:
                    if os.path.exists(blink_file):
                        try:
                            os.remove(blink_file)
                            blink_frames_remaining = 180 # 3 seconds at 60 FPS
                            if hwnd:
                                import sys
                                if sys.platform == "win32":
                                    import ctypes
                                    ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                        except:
                            pass
    
                # Cập nhật event loop của Tkinter ẩn để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
                try:
                    hidden_root.update()
                except Exception:
                    pass
     
                global client_host_resolution
                if client_host_resolution is not None:
                    new_host_w, new_host_h = client_host_resolution
                    client_host_resolution = None
                    if new_host_w != host_w or new_host_h != host_h:
                        print(f"[Client] Host resolution changed from {host_w}x{host_h} to {new_host_w}x{new_host_h}")
                        host_w, host_h = new_host_w, new_host_h
                        
                        import sys
                        if sys.platform == "win32":
                            import ctypes
                            client_max_w = ctypes.windll.user32.GetSystemMetrics(0) - 100
                            client_max_h = ctypes.windll.user32.GetSystemMetrics(1) - 100
                        else:
                            info = pygame.display.Info()
                            client_max_w = info.current_w - 100 if info.current_w > 100 else 1000
                            client_max_h = info.current_h - 100 if info.current_h > 100 else 1000
                        
                        ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
                        window_w = int(host_w * ratio)
                        window_h = int(host_h * ratio)
                        
                        window_w = max(100, window_w)
                        window_h = max(100, window_h)
                        
                        uninstall_keyboard_hook()
                        pygame.display.quit()
                        pygame.display.init()
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                        
                        comp_to_use = client_host_computer_name_override if client_host_computer_name_override else computer_name
                        if comp_to_use:
                            pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=comp_to_use))
                        else:
                            pygame.display.set_caption(_("P2P Remote Desktop Viewer"))
                        try:
                            icon_path = os.path.join(app_dir, "app_icon.png")
                            if os.path.exists(icon_path):
                                pygame.display.set_icon(pygame.image.load(icon_path))
                        except Exception:
                            pass
                            
                        hwnd = None
                        try: hwnd = pygame.display.get_wm_info().get("window")
                        except: pass
                        if hwnd:
                            if clipboard_sync_manager: clipboard_sync_manager.pygame_hwnd = hwnd
                            install_keyboard_hook(hwnd, send_event)

                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})

                # Calculate floating button rectangle dynamically
                min_btn_w, min_btn_h = 40, 22
                cad_btn_w, cad_btn_h = 145, 22
                eye_btn_w, eye_btn_h = 30, 22
                file_btn_w, file_btn_h = 110, 22
                power_btn_w, power_btn_h = 40, 22
                rec_btn_w, rec_btn_h = 30, 22
                close_btn_w, close_btn_h = 40, 22
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                
                show_cad_button = show_buttons and not is_android
                show_file_button = show_buttons and is_android
                show_power_button = show_buttons and is_android
                
                host_os = globals().get('client_host_os_release', '10')
                is_host_windows = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in host_os
                if not is_host_windows:
                    cad_btn_w = 80
                
                # Hide privacy eye button if host is Windows 7 or 8.
                show_eye_button = show_cad_button and is_host_windows and (host_os not in ["7", "8", "8.1", "post2008Server", "post2012Server"])
                
                total_w = 0
                if show_buttons:
                    total_w = min_btn_w + 10 + (file_btn_w + 10 if show_file_button else 0) + (power_btn_w + 10 if show_power_button else 0) + (eye_btn_w + 10 if show_eye_button else 0) + (cad_btn_w + 10 if show_cad_button else 0) + rec_btn_w + 10 + close_btn_w
                    
                start_x = (window_w - total_w) // 2
                
                if show_buttons:
                    min_btn_rect = pygame.Rect(start_x, 0, min_btn_w, min_btn_h)
                    current_x = start_x + min_btn_w + 10
                    
                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_eye_button:
                        eye_btn_rect = pygame.Rect(current_x, 0, eye_btn_w, eye_btn_h)
                        current_x += eye_btn_w + 10
                    else:
                        eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_cad_button:
                        cad_btn_rect = pygame.Rect(current_x, 0, cad_btn_w, cad_btn_h)
                        current_x += cad_btn_w + 10
                    else:
                        cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    rec_btn_rect = pygame.Rect(current_x, 0, rec_btn_w, rec_btn_h)
                    current_x += rec_btn_w + 10
                    close_btn_rect = pygame.Rect(current_x, 0, close_btn_w, close_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    file_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    power_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    rec_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_buttons else False
                file_is_hover = file_btn_rect.collidepoint(mx, my) if show_buttons else False
                power_is_hover = power_btn_rect.collidepoint(mx, my) if show_buttons else False
                eye_is_hover = eye_btn_rect.collidepoint(mx, my) if show_buttons else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_buttons else False
                rec_is_hover = rec_btn_rect.collidepoint(mx, my) if show_buttons else False
                close_is_hover = close_btn_rect.collidepoint(mx, my) if show_buttons else False
     
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        exit_due_to_disconnect = False
                        client_running = False
                        outer_running = False
                        break
                        
                    elif event.type == pygame.VIDEORESIZE:
                        window_w, window_h = event.w, event.h
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
                        
                    elif event.type == pygame.MOUSEMOTION:
                        if show_buttons and (min_btn_rect.collidepoint(event.pos) or file_btn_rect.collidepoint(event.pos) or power_btn_rect.collidepoint(event.pos) or eye_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or rec_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)):
                            continue
                        mx_pos, my_pos = event.pos
                        host_x = int(mx_pos * (host_w / window_w))
                        host_y = int(my_pos * (host_h / window_h))
                        
                        if is_android and drag_start_pos is not None:
                            # Record drag path points for Android swipes/patterns
                            if not drag_path:
                                drag_path.append(drag_start_pos)
                            
                            last_pt = drag_path[-1]
                            # Record point if it moved at least 5 pixels (squared distance > 25) to avoid excessive points
                            if (host_x - last_pt[0])**2 + (host_y - last_pt[1])**2 > 25:
                                drag_path.append((host_x, host_y))
                        else:
                            send_event({"type": "mouse_move", "x": host_x, "y": host_y})
                        
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        if show_buttons and min_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Minimize Button Clicked. Minimizing viewer.")
                                pygame.display.iconify()
                            continue
                        if show_buttons and file_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                import utils.file_manager as fm
                                if hasattr(fm, 'fm_top') and fm.fm_top:
                                    try:
                                        if fm.fm_top.winfo_exists():
                                            def restore_fm():
                                                fm.fm_top.deiconify()
                                                fm.fm_top.focus_force()
                                            fm.fm_top.after(0, restore_fm)
                                            continue
                                    except: pass

                                print("[Client] Transfer File Button Clicked.")
                                hwnd = pygame.display.get_wm_info().get("window")
                                comp_to_use = client_host_computer_name_override if client_host_computer_name_override else computer_name
                                threading.Thread(target=fm.open_transfer_window, args=(comp_to_use, is_android, send_event, hwnd, window_w, window_h), daemon=True).start()
                            continue
                        if show_buttons and power_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Power Button Clicked. Sending power key event to Android.")
                                send_event({"type": "key_event", "key": "power", "pressed": True})
                            continue
                        if show_buttons and eye_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Eye Button Clicked. Sending toggle_screen_cover to host.")
                                state = globals().get('viewer_cover_state', False)
                                globals()['viewer_cover_state'] = not state
                                send_event({"type": "toggle_screen_cover"})
                            continue
                        if show_buttons and cad_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                is_host_win = globals().get('client_host_os_release', '10') in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in globals().get('client_host_os_release', '10')
                                if is_host_win:
                                    print("[Client] CAD Button Clicked. Sending trigger_sas to host.")
                                    send_event({"type": "trigger_sas"})
                                else:
                                    print("[Client] Terminal Button Clicked. Sending trigger_terminal to host.")
                                    send_event({"type": "trigger_terminal"})
                            continue
                        if show_buttons and rec_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                import cv2 as _cv2
                                import os as _os
                                import datetime as _datetime
                                state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                                
                                state['is_recording'] = not state['is_recording']
                                if state['is_recording']:
                                    print("[Client] Started recording viewer...")
                                    c_name = client_host_computer_name_override if client_host_computer_name_override else computer_name
                                    c_name = c_name if c_name else "host"
                                    # Replace invalid chars from computer name
                                    c_name = "".join([c if c.isalnum() else "_" for c in c_name])
                                    filename = f"{c_name}_{_datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
                                    videos_dir = _os.path.join(_os.path.expanduser('~'), 'Videos')
                                    _os.makedirs(videos_dir, exist_ok=True)
                                    filepath = _os.path.join(videos_dir, filename)
                                    
                                    fourcc = _cv2.VideoWriter_fourcc(*'mp4v')
                                    state['writer'] = _cv2.VideoWriter(filepath, fourcc, 20.0, (host_w, host_h))
                                    state['size'] = (host_w, host_h)
                                else:
                                    print("[Client] Stopped recording viewer.")
                                    if state['writer']:
                                        state['writer'].release()
                                        state['writer'] = None
                                        
                                globals()['viewer_record_state'] = state
                            continue

                        if show_buttons and close_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Close Button Clicked. Exiting viewer.")
                                pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue
                        if event.button in button_map:
                            mx_pos, my_pos = event.pos
                            host_x = int(mx_pos * (host_w / window_w))
                            host_y = int(my_pos * (host_h / window_h))
                            
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                drag_start_pos = (host_x, host_y)
                                drag_start_time = time.time()
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": True,
                                    "x": host_x,
                                    "y": host_y
                                })
                            else: # MOUSEBUTTONUP
                                if drag_start_pos and is_android:
                                    dx = host_x - drag_start_pos[0]
                                    dy = host_y - drag_start_pos[1]
                                    if (dx*dx + dy*dy) > 400 or len(drag_path) > 3: # distance > 20 pixels or multi-point path
                                        duration = int((time.time() - drag_start_time) * 1000)
                                        duration = max(200, min(duration, 3000))
                                        
                                        if drag_path and drag_path[-1] != (host_x, host_y):
                                            drag_path.append((host_x, host_y))
                                            
                                        if len(drag_path) > 3:
                                            # Subsample if too many points to avoid massive payloads
                                            if len(drag_path) > 50:
                                                step = len(drag_path) / 50.0
                                                subsampled_path = [drag_path[int(i*step)] for i in range(50)]
                                                if subsampled_path[-1] != drag_path[-1]:
                                                    subsampled_path.append(drag_path[-1])
                                                drag_path = subsampled_path
                                                
                                            send_event({
                                                "type": "mouse_swipe_path",
                                                "path": drag_path,
                                                "duration": duration
                                            })
                                        else:
                                            send_event({
                                                "type": "mouse_swipe",
                                                "x1": drag_start_pos[0],
                                                "y1": drag_start_pos[1],
                                                "x2": host_x,
                                                "y2": host_y,
                                                "duration": duration
                                            })
                                        drag_start_pos = None
                                        drag_path = []
                                        continue
                                        
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": False,
                                    "x": host_x,
                                    "y": host_y
                                })
                                drag_start_pos = None
                                drag_path = []
                            
                    elif event.type == pygame.MOUSEWHEEL:
                        send_event({"type": "mouse_scroll", "dx": event.x, "dy": event.y})
                        
                    elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                        key_name = pygame.key.name(event.key)
                        
                        char_to_send = key_name
                        if event.type == pygame.KEYDOWN:
                            if is_android:
                                # Handle Ctrl+V (Paste) directly by fetching PC clipboard and sending paste_text
                                if event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                                    try:
                                        clip_text = get_clipboard_text()
                                        if clip_text:
                                            send_event({
                                                "type": "paste_text",
                                                "text": clip_text
                                            })
                                    except Exception as e:
                                        print(f"[Client] Lỗi paste Ctrl+V: {e}")
                                    continue
                                    
                                # For Android, we inject characters directly into text fields using Accessibility.
                                # Therefore, we MUST use event.unicode to capture Shift modifications (e.g. 'A' instead of 'a').
                                # We also map special keys to their string equivalents.
                                if hasattr(event, 'unicode'):
                                    print(f"[DEBUG KEY] name='{key_name}', unicode='{event.unicode}', mod={event.mod}")
                                    
                                if key_name == "space":
                                    char_to_send = " "
                                elif key_name == "tab":
                                    char_to_send = "tab"
                                elif key_name == "return" or key_name == "enter":
                                    char_to_send = "enter" # handled by Android handleKey
                                elif key_name == "backspace":
                                    char_to_send = "backspace"
                                elif hasattr(event, 'unicode') and event.unicode and len(event.unicode) > 0 and ord(event.unicode[0]) >= 32:
                                    char_to_send = event.unicode
                                else:
                                    if key_name in ["escape", "home", "menu", "volume up", "volume down", "delete", "up", "down", "left", "right"]:
                                        char_to_send = key_name
                                    else:
                                        active_unicode_map[event.key] = ""
                                        continue
                            else:
                                # For Windows hosts, send raw key_name for letters/digits so host IME can compose
                                if len(key_name) == 1 and (key_name.isalpha() or key_name.isdigit()):
                                    char_to_send = key_name  # Raw key, let host IME handle it
                                elif hasattr(event, 'unicode') and event.unicode and len(event.unicode) == 1 and ord(event.unicode) >= 32:
                                    if key_name not in ['space', 'delete', 'home', 'end', 'page up', 'page down', 'insert', 'escape', 'tab', 'backspace', 'return', 'enter']:
                                        char_to_send = event.unicode
                            
                            active_unicode_map[event.key] = char_to_send
                        else:
                            char_to_send = active_unicode_map.get(event.key, key_name)
                            if event.key in active_unicode_map:
                                del active_unicode_map[event.key]
                                
                        send_event({
                            "type": "key_event",
                            "key": char_to_send,
                            "pressed": event.type == pygame.KEYDOWN
                        })
                        
                # Draw frame
                with client_frame_lock:
                    frame_to_draw = client_latest_frame
                    
                if frame_to_draw is not None:
                    w, h = frame_to_draw.size
                    surf = pygame.image.fromstring(frame_to_draw.tobytes(), (w, h), 'RGB')
                    # smoothscale sử dụng bilinear interpolation thay vì nearest-neighbor
                    # cho chất lượng upscale mượt hơn nhiều (đặc biệt khi xem Android 1080p)
                    scaled_surf = pygame.transform.smoothscale(surf, (window_w, window_h))
                    screen.blit(scaled_surf, (0, 0))
                    
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    if state['is_recording'] and state['writer']:
                        try:
                            import cv2 as _cv2
                            import numpy as _np
                            frame_arr = _np.array(frame_to_draw)
                            bgr_frame = _cv2.cvtColor(frame_arr, _cv2.COLOR_RGB2BGR)
                            
                            record_size = state.get('size', (host_w, host_h))
                            if bgr_frame.shape[1] != record_size[0] or bgr_frame.shape[0] != record_size[1]:
                                bgr_frame = _cv2.resize(bgr_frame, record_size)
                            
                            # Draw beautiful anti-aliased mouse cursor overlay for recording
                            mx, my = pygame.mouse.get_pos()
                            if pygame.mouse.get_focused() and 0 <= mx <= window_w and 0 <= my <= window_h:
                                hx = int(mx * (w / window_w)) if window_w else 0
                                hy = int(my * (h / window_h)) if window_h else 0
                                pts = _np.array([
                                    [hx, hy], [hx, hy + 17], [hx + 4, hy + 13],
                                    [hx + 9, hy + 23], [hx + 12, hy + 21],
                                    [hx + 7, hy + 11], [hx + 14, hy + 11]
                                ], _np.int32)
                                _cv2.fillPoly(bgr_frame, [pts], (255, 255, 255), lineType=_cv2.LINE_AA)
                                _cv2.polylines(bgr_frame, [pts], True, (0, 0, 0), 1, lineType=_cv2.LINE_AA)
                                
                            state['writer'].write(bgr_frame)
                        except Exception as e:
                            print(f"[Client] Recording error: {e}")
                else:
                    if pygame_theme == "light":
                        screen.fill((240, 240, 245))
                    elif pygame_theme == "gray":
                        screen.fill((82, 89, 98))
                    elif pygame_theme == "pink":
                        screen.fill((255, 240, 245))
                    elif pygame_theme == "crystal":
                        screen.fill((224, 247, 250))
                    elif pygame_theme == "orange":
                        screen.fill((255, 243, 224))
                    elif pygame_theme == "red":
                        screen.fill((255, 235, 238))
                    else:
                        screen.fill((30, 30, 30))
                    
                # Draw red border if blinking (focus requested)
                if blink_frames_remaining > 0:
                    if (blink_frames_remaining // 15) % 2 == 0:
                        border_rect = pygame.Rect(0, 0, window_w, window_h)
                        pygame.draw.rect(screen, (255, 0, 0), border_rect, width=10)
                    blink_frames_remaining -= 1
                    
                # Draw floating buttons on top
                if show_buttons:
                    # Minimize button
                    min_bg_color = (51, 153, 255) if min_is_hover else (0, 102, 204)
                    min_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, min_bg_color, min_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, min_border_color, min_btn_rect, width=1, border_radius=4)
                    
                    min_text_surf = btn_font.render("_", True, (255, 255, 255))
                    min_text_rect = min_text_surf.get_rect(center=min_btn_rect.center)
                    min_text_rect.y -= 2 # Adjust slightly up to center visually
                    screen.blit(min_text_surf, min_text_rect)

                    # Extract common border color for buttons
                    if pygame_theme == "light":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "gray":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "pink":
                        btn_border_color = (255, 105, 180)
                    elif pygame_theme == "crystal":
                        btn_border_color = (128, 222, 234)
                    elif pygame_theme == "orange":
                        btn_border_color = (255, 167, 38)
                    elif pygame_theme == "red":
                        btn_border_color = (229, 57, 53)
                    else:
                        btn_border_color = (0, 173, 181)

                    # CAD / File buttons
                    if show_cad_button or show_file_button:
                        if pygame_theme == "light":
                            cad_bg_color = (220, 220, 235) if cad_is_hover else (245, 245, 255)
                            file_bg_color = (220, 220, 235) if file_is_hover else (245, 245, 255)
                            cad_text_color = (40, 40, 50)
                            file_text_color = (40, 40, 50)
                        elif pygame_theme == "gray":
                            cad_bg_color = (99, 106, 115) if cad_is_hover else (82, 89, 98)
                            file_bg_color = (99, 106, 115) if file_is_hover else (82, 89, 98)
                            cad_text_color = (240, 240, 240)
                            file_text_color = (240, 240, 240)
                        elif pygame_theme == "pink":
                            cad_bg_color = (255, 105, 180) if cad_is_hover else (255, 182, 193)
                            file_bg_color = (255, 105, 180) if file_is_hover else (255, 182, 193)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "crystal":
                            cad_bg_color = (38, 198, 218) if cad_is_hover else (0, 188, 212)
                            file_bg_color = (38, 198, 218) if file_is_hover else (0, 188, 212)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "orange":
                            cad_bg_color = (255, 183, 77) if cad_is_hover else (255, 152, 0)
                            file_bg_color = (255, 183, 77) if file_is_hover else (255, 152, 0)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "red":
                            cad_bg_color = (239, 154, 154) if cad_is_hover else (244, 67, 54)
                            file_bg_color = (239, 154, 154) if file_is_hover else (244, 67, 54)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        else:
                            cad_bg_color = (58, 58, 77) if cad_is_hover else (42, 42, 53)
                            file_bg_color = (58, 58, 77) if file_is_hover else (42, 42, 53)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        
                        if show_file_button:
                            pygame.draw.rect(screen, file_bg_color, file_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, file_btn_rect, width=1, border_radius=4)
                            
                            file_text_surf = btn_font.render(_("Chuyển tệp"), True, file_text_color)
                            file_text_rect = file_text_surf.get_rect(center=file_btn_rect.center)
                            screen.blit(file_text_surf, file_text_rect)

                        if show_power_button:
                            import math
                            cx, cy = power_btn_rect.center
                            
                            # Nền nút hình chữ nhật xám giống nút quay video
                            power_bg_color = (80, 80, 80) if power_is_hover else (50, 50, 50)
                            if pygame_theme in ["light", "crystal", "orange", "red"]:
                                power_bg_color = (220, 220, 235) if power_is_hover else (245, 245, 255)
                            pygame.draw.rect(screen, power_bg_color, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)

                            # Nền hình tròn xanh lá như hình đính kèm
                            bg_color = (40, 190, 80) if power_is_hover else (30, 170, 70)
                            pygame.draw.circle(screen, bg_color, (cx, cy), 10)
                            pygame.draw.circle(screen, btn_border_color, (cx, cy), 10, 1)

                            # Icon Power màu trắng, nét đơn (1px)
                            r = 5
                            # Vòng cung khuyết ở trên
                            pygame.draw.arc(screen, (255, 255, 255), (cx - r, cy - r, r * 2, r * 2), math.pi/2 + 0.65, 2.5 * math.pi - 0.65, 1)
                            # Dấu | ở giữa (nét đơn)
                            pygame.draw.line(screen, (255, 255, 255), (cx, cy - r - 1), (cx, cy + 1), 1)

                        if show_cad_button:
                            # Draw Eye Button
                            eye_bg = (100, 100, 100) if globals().get('viewer_cover_state', False) else cad_bg_color
                            if eye_is_hover and not globals().get('viewer_cover_state', False):
                                pass # cad_bg_color already has hover color assigned
                            elif eye_is_hover:
                                eye_bg = (130, 130, 130)
                            
                            pygame.draw.rect(screen, eye_bg, eye_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, eye_btn_rect, width=1, border_radius=4)
                            
                            eye_icon_rect = pygame.Rect(0, 0, 16, 10)
                            eye_icon_rect.center = eye_btn_rect.center
                            pygame.draw.ellipse(screen, cad_text_color, eye_icon_rect, width=1)
                            pygame.draw.circle(screen, cad_text_color, eye_icon_rect.center, 3)

                            # Draw CAD Button
                            pygame.draw.rect(screen, cad_bg_color, cad_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, cad_btn_rect, width=1, border_radius=4)
                            
                            is_host_win = globals().get('client_host_os_release', '10') in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in globals().get('client_host_os_release', '10')
                            cad_text_str = "Ctrl + Alt + Delete" if is_host_win else "Terminal"
                            cad_text_surf = btn_font.render(cad_text_str, True, cad_text_color)
                            cad_text_rect = cad_text_surf.get_rect(center=cad_btn_rect.center)
                            screen.blit(cad_text_surf, cad_text_rect)
                    
                    # Record button (Red circle)
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    rec_bg_color = (80, 80, 80) if rec_is_hover else (50, 50, 50)
                    if pygame_theme in ["light", "crystal", "orange", "red"]:
                        rec_bg_color = (220, 220, 235) if rec_is_hover else (245, 245, 255)
                    
                    pygame.draw.rect(screen, rec_bg_color, rec_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, btn_border_color, rec_btn_rect, width=1, border_radius=4)
                    
                    if state['is_recording']:
                        pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(rec_btn_rect.centerx - 4, rec_btn_rect.centery - 4, 8, 8))
                    else:
                        pygame.draw.circle(screen, (255, 0, 0), rec_btn_rect.center, 5)
                        
                    if state['is_recording']:
                        import time as _time
                        if int(_time.time() * 2) % 2 == 0:
                            # Make the icon dim to simulate blinking
                            dim_surf = pygame.Surface(rec_btn_rect.size, pygame.SRCALPHA)
                            dim_surf.fill((0, 0, 0, 128))
                            screen.blit(dim_surf, rec_btn_rect.topleft)

                    # Close button (Red X)
                    close_bg_color = (255, 77, 77) if close_is_hover else (204, 0, 0)
                    close_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, close_bg_color, close_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, close_border_color, close_btn_rect, width=1, border_radius=4)
                    
                    close_text_surf = btn_font.render("X", True, (255, 255, 255))
                    close_text_rect = close_text_surf.get_rect(center=close_btn_rect.center)
                    screen.blit(close_text_surf, close_text_rect)
                    
                current_countdown = globals().get('client_switching_desktop_countdown', 0)
                if current_countdown > 0:
                    if not was_switching:
                        was_switching = True
                        switching_last_tick = pygame.time.get_ticks()
                        switching_start_tick = pygame.time.get_ticks()
                    
                    if "msg_font" not in locals():
                        try: msg_font = pygame.font.SysFont(font_names, 24, bold=True)
                        except: msg_font = pygame.font.Font(None, 32)
                    
                    overlay = pygame.Surface((window_w, window_h))
                    overlay.set_alpha(150)
                    overlay.fill((0, 0, 0))
                    screen.blit(overlay, (0, 0))
                    
                    elapsed_switching = pygame.time.get_ticks() - switching_start_tick
                    if elapsed_switching > 3000:
                        text_msg = _("Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host...")
                    else:
                        text_msg = _("Đang chuyển giao diện... Vui lòng đợi ") + str(current_countdown) + _(" giây...")
                    
                    text_surf = msg_font.render(text_msg, True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                    screen.blit(text_surf, text_rect)
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - switching_last_tick >= 1000:
                        client_switching_desktop_countdown = max(0, current_countdown - 1)
                        switching_last_tick = current_tick
                        if client_switching_desktop_countdown == 0:
                            was_switching = False
                            send_event({"type": "check_domain"})
                elif was_switching:
                    was_switching = False
                    send_event({"type": "check_domain"})
                
                if client_last_recv_time > 0 and time.time() - client_last_recv_time > 10.0:
                    print("[Client] Connection ping timeout. Disconnecting.")
                    # Nếu host là Linux/Ubuntu, ping timeout thường do shutdown/restart
                    host_os = globals().get('client_host_os_release', '10')
                    is_host_windows = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in str(host_os)
                    if not is_host_windows:
                        print("[Client] Non-Windows host ping timeout. Treating as host shutdown.")
                        client_host_did_shutdown = True
                    exit_due_to_disconnect = True
                    client_running = False
                    break

                pygame.display.flip()
                clock.tick(60)
                
            uninstall_keyboard_hook()
            
            state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
            if state['writer']:
                state['writer'].release()
                state['writer'] = None
                state['is_recording'] = False
                globals()['viewer_record_state'] = state
            
            if exit_due_to_disconnect and not client_host_did_shutdown and reconnect_queue:
                countdown = 60
                last_tick = pygame.time.get_ticks()
                try: msg_font = pygame.font.SysFont(font_names, 24, bold=True)
                except: msg_font = pygame.font.Font(None, 32)
                
                print("[Client] Disconnected. Requesting reconnect in background...")
                try: reconnect_queue.put("RECONNECT_REQUEST")
                except: pass
                
                status_msg_text = None
                
                while countdown > 0 and outer_running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            countdown = 0
                            exit_due_to_disconnect = False
                            outer_running = False
                    
                    if not outer_running:
                        break
                        
                    sock_acquired = False
                    try:
                        while True:
                            new_sock = reconnect_queue.get_nowait()
                            if isinstance(new_sock, str) and new_sock.startswith("STATUS|"):
                                status_msg_text = new_sock.split("|", 1)[1]
                                continue
                            elif new_sock == "FAILED":
                                print("[Client] Reconnection failed. Closing window.")
                                outer_running = False
                                break
                            elif isinstance(new_sock, tuple) and new_sock[0] == "SHARED_SOCK":
                                print("[Client] Received shared socket. Resuming session!")
                                sock = socket.fromshare(new_sock[1])
                                if partner_pass:
                                    socket_passwords[sock] = partner_pass
                                sock_acquired = True
                                break # Break inner wait loop
                            elif hasattr(new_sock, 'fileno'):
                                print("[Client] Received new socket. Resuming session!")
                                sock = new_sock
                                if partner_pass:
                                    socket_passwords[sock] = partner_pass
                                sock_acquired = True
                                break # Break inner wait loop
                    except Exception as re_err:
                        pass # Ignore queue.Empty
                        
                    if not outer_running or sock_acquired:
                        break
                    
                    screen.fill((30, 30, 30))
                    
                    if status_msg_text:
                        text_surf = msg_font.render(_("Trạng thái: ") + str(status_msg_text), True, (255, 165, 0))
                        text_rect = text_surf.get_rect(center=(window_w//2, window_h//2 - 20))
                        screen.blit(text_surf, text_rect)
                        
                        cd_surf = msg_font.render(_("Thời gian chờ: ") + str(countdown) + _(" giây..."), True, (255, 255, 255))
                        cd_rect = cd_surf.get_rect(center=(window_w//2, window_h//2 + 20))
                        screen.blit(cd_surf, cd_rect)
                    else:
                        text_surf = msg_font.render(_("Mất kết nối. Đang thử kết nối lại... ") + str(countdown) + _(" giây..."), True, (255, 255, 255))
                        text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                        screen.blit(text_surf, text_rect)
                        
                    pygame.display.flip()
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - last_tick >= 1000:
                        countdown -= 1
                        last_tick = current_tick
                        
                    clock.tick(30)
                    
                if outer_running and countdown == 0:
                    print("[Client] Reconnect timeout. Closing window.")
                    outer_running = False
                    
                if outer_running:
                    continue # Jump back to the start of the outer_running loop!
                    
            # If we reach here, we are truly exiting
            outer_running = False
            
        uninstall_keyboard_hook()
        # pygame.quit() # Bỏ qua để tránh deadlock SetParent với Tkinter thread
        try: log_activity(_("Ngừng điều khiển ID ") + str(partner_id) + " (" + str(computer_name) + ")")
        except: pass
        import os
        if exit_due_to_disconnect:
            print("[Client] Viewer exited due to disconnect. Exit code 99.")
            os._exit(99)
        os._exit(0)
    except Exception as critical_e:
        uninstall_keyboard_hook()
        import traceback
        with open("client_crash.log", "w", encoding="utf-8") as f:
            f.write(f"CRITICAL ERROR IN VIEWER LOOP:\n{traceback.format_exc()}\n")
        # try: pygame.quit()
        # except: pass
        import os
        if exit_due_to_disconnect:
            os._exit(99)
        os._exit(1)

