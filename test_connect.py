import socket
import sys

host = 'homed.auavn.com'
port = 8765

try:
    print(f'Testing {host}:{port}...')
    sock = socket.create_connection((host, port), timeout=5)
    print('Connected successfully!')
    sock.sendall(b'{"action":"ping"}\n')
    data = sock.recv(1024)
    print('Received:', data)
except Exception as e:
    print('Error:', type(e).__name__, e)
