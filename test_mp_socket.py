import socket
import multiprocessing as mp
import time
import os

def child_process(sock):
    try:
        sock.sendall(b"Hello from child!")
        print("Child sent data successfully.")
    except Exception as e:
        print(f"Child error: {e}")

if __name__ == "__main__":
    mp.freeze_support()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    port = server.getsockname()[1]
    
    def accept_conn():
        conn, _ = server.accept()
        print("Server accepted connection.")
        data = conn.recv(1024)
        print(f"Server received: {data}")
        conn.close()
        
    import threading
    threading.Thread(target=accept_conn, daemon=True).start()
    
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', port))
    
    p = mp.Process(target=child_process, args=(client,))
    p.start()
    client.close()
    p.join()
    print("Done.")
