import socket
import threading
import json
import struct
import time
import mss
import cv2
import numpy as np
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

PORT = 9999
HOST = '0.0.0.0' # Listen on all interfaces

# Controller instances
mouse = MouseController()
keyboard = KeyboardController()

# Button mapping for mouse clicks
button_map = {
    'left': Button.left,
    'right': Button.right,
    'middle': Button.middle
}

# Key mapping from Pygame key names to pynput Key
key_map = {
    'space': Key.space,
    'enter': Key.enter,
    'return': Key.enter,
    'escape': Key.esc,
    'backspace': Key.backspace,
    'tab': Key.tab,
    'left shift': Key.shift,
    'right shift': Key.shift_r,
    'left ctrl': Key.ctrl_l,
    'right ctrl': Key.ctrl_r,
    'left alt': Key.alt_l,
    'right alt': Key.alt_r,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'caps lock': Key.caps_lock,
    'capslock': Key.caps_lock,
    'delete': Key.delete,
    'home': Key.home,
    'end': Key.end,
    'page up': Key.page_up,
    'page down': Key.page_down,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
}

running = True

def send_msg(sock, data_bytes):
    msg = struct.pack('>I', len(data_bytes)) + data_bytes
    sock.sendall(msg)

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def recv_msg(sock):
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack('>I', length_bytes)[0]
    return recv_exact(sock, length)

def release_all_modifiers():
    print("[Host] Releasing all modifier keys...")
    for mod_key in [Key.shift, Key.ctrl, Key.alt]:
        try:
            keyboard.release(mod_key)
        except:
            pass

def sender_thread(conn, monitor):
    global running
    print("[Host] Started Screen Sender Thread.")
    with mss.mss() as sct:
        while running:
            try:
                # Capture screen
                img = sct.grab(monitor)
                frame = np.array(img)
                # Convert to BGR (OpenCV)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Compress to JPEG
                _, jpeg_bytes = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                jpeg_data = jpeg_bytes.tobytes()
                
                # Send to client
                send_msg(conn, jpeg_data)
                
                # Control FPS (Approx 25-30 FPS)
                time.sleep(0.035)
            except Exception as e:
                print(f"[Host] Sender Thread Exception: {e}")
                break
    print("[Host] Screen Sender Thread Stopped.")

def receiver_thread(conn):
    global running
    print("[Host] Started Input Receiver Thread.")
    while running:
        try:
            msg = recv_msg(conn)
            if not msg:
                print("[Host] Client disconnected.")
                break
                
            event = json.loads(msg.decode('utf-8'))
            handle_event(event)
        except Exception as e:
            print(f"[Host] Receiver Thread Exception: {e}")
            break
    print("[Host] Input Receiver Thread Stopped.")
    release_all_modifiers()

def handle_event(event):
    ev_type = event.get('type')
    if ev_type == 'mouse_move':
        x, y = event['x'], event['y']
        mouse.position = (x, y)
    elif ev_type == 'mouse_click':
        btn = button_map.get(event['button'])
        if btn:
            if event['pressed']:
                mouse.press(btn)
            else:
                mouse.release(btn)
    elif ev_type == 'mouse_scroll':
        dx, dy = event['dx'], event['dy']
        # Pygame scroll wheel event dy is vertical scroll.
        # positive dy means scroll up, negative dy means scroll down.
        # pynput mouse.scroll(dx, dy) uses positive values for up/right, negative for down/left.
        # In pygame 2.0+ event.y is 1 for up, -1 for down.
        mouse.scroll(dx, dy)
    elif ev_type == 'key_event':
        key_name = event['key']
        pressed = event['pressed']
        
        target_key = None
        if key_name in key_map:
            target_key = key_map[key_name]
        elif len(key_name) == 1:
            target_key = key_name
            
        if target_key:
            try:
                if pressed:
                    keyboard.press(target_key)
                else:
                    keyboard.release(target_key)
            except Exception as e:
                print(f"[Host] Error simulating key '{key_name}': {e}")

def main():
    global running
    print("=" * 60)
    print("      PYTHON P2P REMOTE DESKTOP - AGENT (HOST)")
    print("=" * 60)
    
    # Get Primary Monitor Specs
    with mss.mss() as sct:
        monitor = sct.monitors[1] # Primary monitor
        host_w = monitor['width']
        host_h = monitor['height']
        print(f"[Host] Primary Screen Resolution: {host_w}x{host_h}")
    
    # Create TCP Server Socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Reuse address
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(1)
        print(f"[Host] Listening for connections on port {PORT}...")
        print("[Host] Ensure Port Forwarding is set on your router for port 9999 if connecting via Internet!")
    except Exception as e:
        print(f"[Host] Failed to bind to port {PORT}: {e}")
        return

    try:
        while True:
            conn, addr = server.accept()
            print(f"[Host] Accepted connection from {addr[0]}:{addr[1]}")
            
            # Send screen resolution info to Client
            res_info = json.dumps({"width": host_w, "height": host_h}).encode('utf-8')
            try:
                send_msg(conn, res_info)
            except Exception as e:
                print(f"[Host] Failed to send resolution info: {e}")
                conn.close()
                continue
                
            running = True
            
            # Start Sender & Receiver threads
            t_sender = threading.Thread(target=sender_thread, args=(conn, monitor))
            t_receiver = threading.Thread(target=receiver_thread, args=(conn,))
            
            t_sender.daemon = True
            t_receiver.daemon = True
            
            t_sender.start()
            t_receiver.start()
            
            # Wait for receiver to finish (implies disconnection)
            t_receiver.join()
            running = False
            t_sender.join()
            
            conn.close()
            print("[Host] Connection closed. Waiting for new client...")
    except KeyboardInterrupt:
        print("\n[Host] Shutting down agent.")
    finally:
        server.close()

if __name__ == '__main__':
    main()
