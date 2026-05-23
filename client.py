import socket
import threading
import json
import struct
import cv2
import numpy as np
import pygame
import sys

pygame.init()

# Shared frame buffer
frame_lock = threading.Lock()
latest_frame = None
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

def receiver_thread(sock):
    global latest_frame, running
    print("[Client] Receiver thread started.")
    while running:
        try:
            msg = recv_msg(sock)
            if not msg:
                print("[Client] Server closed connection.")
                running = False
                break
                
            # Decode JPEG
            np_arr = np.frombuffer(msg, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is not None:
                # Convert BGR to RGB for Pygame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                with frame_lock:
                    latest_frame = frame_rgb
        except Exception as e:
            print(f"[Client] Error receiving screen frame: {e}")
            running = False
            break
    print("[Client] Receiver thread stopped.")

def main():
    global latest_frame, running
    
    print("=" * 60)
    print("      PYTHON P2P REMOTE DESKTOP - CONTROLLER (CLIENT)")
    print("=" * 60)
    
    # Input Host Connection Info
    host_ip = input("Enter Host IP (default: 127.0.0.1): ").strip()
    if not host_ip:
        host_ip = '127.0.0.1'
        
    host_port_str = input("Enter Host Port (default: 9999): ").strip()
    if not host_port_str:
        host_port = 9999
    else:
        host_port = int(host_port_str)
        
    print(f"[Client] Connecting to {host_ip}:{host_port}...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host_ip, host_port))
        print("[Client] Connected successfully!")
    except Exception as e:
        print(f"[Client] Failed to connect: {e}")
        return

    # Receive screen dimensions from Host
    try:
        res_msg = recv_msg(sock)
        if not res_msg:
            print("[Client] Failed to receive screen resolution from Host.")
            sock.close()
            return
        res_info = json.loads(res_msg.decode('utf-8'))
        host_w = res_info['width']
        host_h = res_info['height']
        print(f"[Client] Host Screen Resolution: {host_w}x{host_h}")
    except Exception as e:
        print(f"[Client] Error during initialization: {e}")
        sock.close()
        return

    # Initialize Pygame Window
    window_w, window_h = 1280, 720
    screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
    pygame.display.set_caption(f"Remote Desktop - Connected to {host_ip}:{host_port}")
    
    # Start the receiver thread
    t_recv = threading.Thread(target=receiver_thread, args=(sock,))
    t_recv.daemon = True
    t_recv.start()
    
    # Helper to send event JSON
    def send_event(event_dict):
        try:
            data = json.dumps(event_dict).encode('utf-8')
            send_msg(sock, data)
        except Exception as e:
            print(f"[Client] Error sending event: {e}")
            
    clock = pygame.time.Clock()
    
    button_map = {1: 'left', 2: 'middle', 3: 'right'}
    
    try:
        while running:
            # Handle Pygame Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                    
                elif event.type == pygame.VIDEORESIZE:
                    window_w, window_h = event.w, event.h
                    screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                    
                elif event.type == pygame.MOUSEMOTION:
                    # Scale coordinates to host screen
                    mx, my = event.pos
                    host_x = int(mx * (host_w / window_w))
                    host_y = int(my * (host_h / window_h))
                    send_event({
                        "type": "mouse_move",
                        "x": host_x,
                        "y": host_y
                    })
                    
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    if event.button in button_map:
                        send_event({
                            "type": "mouse_click",
                            "button": button_map[event.button],
                            "pressed": event.type == pygame.MOUSEBUTTONDOWN
                        })
                        
                elif event.type == pygame.MOUSEWHEEL:
                    # event.x is horizontal, event.y is vertical
                    send_event({
                        "type": "mouse_scroll",
                        "dx": event.x,
                        "dy": event.y
                    })
                    
                elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                    key_name = pygame.key.name(event.key)
                    send_event({
                        "type": "key_event",
                        "key": key_name,
                        "pressed": event.type == pygame.KEYDOWN
                    })
            
            # Render the screen
            with frame_lock:
                frame_to_draw = latest_frame
                
            if frame_to_draw is not None:
                # Convert BGR frame to Pygame Surface
                h, w, _ = frame_to_draw.shape
                surf = pygame.image.frombuffer(frame_to_draw.tobytes(), (w, h), 'RGB')
                # Scale to fit the window size
                scaled_surf = pygame.transform.smoothscale(surf, (window_w, window_h))
                screen.blit(scaled_surf, (0, 0))
                pygame.display.flip()
            else:
                # Black screen with "Connecting..." text if no frame received yet
                screen.fill((30, 30, 30))
                font = pygame.font.SysFont('Arial', 24)
                text = font.render("Waiting for remote screen stream...", True, (200, 200, 200))
                text_rect = text.get_rect(center=(window_w//2, window_h//2))
                screen.blit(text, text_rect)
                pygame.display.flip()
                
            # Limit loop rate
            clock.tick(60)
            
    except KeyboardInterrupt:
        print("[Client] Interrupted by user.")
    finally:
        running = False
        sock.close()
        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    main()
