import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# 1. network/crypto.py
crypto_code = """import hashlib
import struct
import threading
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

send_nonce_counter = 0
send_counter_lock = threading.Lock()

def get_crypto_key(password):
    if not isinstance(password, str):
        if isinstance(password, (list, tuple)) and password:
            password = password[0]
        else:
            password = str(password)
    return hashlib.sha256(password.encode('utf-8')).digest()

def encrypt_payload(data_bytes, password):
    global send_nonce_counter
    key = get_crypto_key(password)
    chacha = ChaCha20Poly1305(key)
    
    with send_counter_lock:
        send_nonce_counter += 1
        current_counter = send_nonce_counter
        
    nonce = struct.pack('>Q', current_counter) + b'\\x00\\x00\\x00\\x00'
    return nonce + chacha.encrypt(nonce, data_bytes, None)

def decrypt_payload(encrypted_bytes, password):
    passwords = [password] if isinstance(password, str) else list(password)
    passwords = [p for p in passwords if p]
    
    if len(encrypted_bytes) < 12:
        raise ValueError(_("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)"))
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    
    last_err = None
    for p in passwords:
        try:
            key = get_crypto_key(p)
            chacha = ChaCha20Poly1305(key)
            return chacha.decrypt(nonce, ciphertext, None)
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError(_("Không giải mã được với bất kỳ mật khẩu nào"))
"""

# 2. network/socket_utils.py
socket_utils_code = """import socket
import struct
import threading
from .crypto import encrypt_payload, decrypt_payload

_socket_send_locks = {}
_socket_send_locks_meta = threading.Lock()
socket_passwords = {}
APP_KEY = "q3tu0y7j"

def _get_socket_send_lock(sock):
    with _socket_send_locks_meta:
        lock = _socket_send_locks.get(sock)
        if lock is None:
            lock = threading.Lock()
            _socket_send_locks[sock] = lock
        return lock

def force_close_socket(sock):
    if not sock: return
    try:
        import struct
        # Set SO_LINGER to abort the connection with RST to avoid TIME_WAIT
        linger = struct.pack('ii', 1, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    except:
        pass
    try:
        sock.close()
    except:
        pass
    # Clean up per-socket lock to prevent memory leaks
    with _socket_send_locks_meta:
        _socket_send_locks.pop(sock, None)
    socket_passwords.pop(sock, None)

def send_msg(sock, data_bytes, password=None):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    try:
        lock = _get_socket_send_lock(sock)
        with lock:
            encrypted_data = encrypt_payload(data_bytes, password)
            msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
            sock.sendall(msg)
    except Exception as e:
        print(f"[Socket] Lỗi gửi dữ liệu: {e}")

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def recv_msg(sock, password=None):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack('>I', length_bytes)[0]
    encrypted_data = recv_exact(sock, length)
    if not encrypted_data:
        return None
    try:
        return decrypt_payload(encrypted_data, password)
    except Exception as e:
        print(f"[Socket] Lỗi giải mã dữ liệu: {e}")
        return b''
"""

# 3. network/upnp.py
upnp_code = """import socket
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from .socket_utils import force_close_socket
from utils.hwid import get_local_ip

# Automatic UPnP Port Forwarding via SSDP and SOAP
def attempt_upnp_forward(internal_port):
    print(f"[UPnP] Attempting automatic port mapping for port {internal_port}...")
    
    # SSDP M-SEARCH Request to find UPnP Router
    ssdp_msg = (
        'M-SEARCH * HTTP/1.1\\n'
        'HOST: 239.255.255.250:1900\\n'
        'MAN: "ssdp:discover"\\n'
        'MX: 2\\n'
        'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\\n'
        '\\n'
    )
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    location_url = None
    
    try:
        sock.sendto(ssdp_msg.encode('utf-8'), ('239.255.255.250', 1900))
        start_time = time.time()
        while time.time() - start_time < 3.0:
            try:
                sock.settimeout(max(0.1, 3.0 - (time.time() - start_time)))
                data, addr = sock.recvfrom(65535)
                response = data.decode('utf-8', errors='ignore')
                for line in response.split('\\n'):
                    if line.upper().startswith('LOCATION:'):
                        location_url = line.split(':', 1)[1].strip()
                        break
                if location_url:
                    break
            except socket.timeout:
                # Timeout is expected when discovering
                continue
    except Exception as e:
        print(f"[UPnP] SSDP discovery timeout/error: {e}")
    finally:
        force_close_socket(sock)
        
    if not location_url:
        print("[UPnP] UPnP Router not found on local network.")
        return False
        
    print(f"[UPnP] Found router XML description at: {location_url}")
    
    try:
        req = urllib.request.Request(location_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        
        def find_tag(element, tag_name):
            for elem in element.iter():
                if elem.tag.endswith(tag_name):
                    return elem
            return None
            
        control_url = None
        service_type = None
        
        for service in root.iter():
            if service.tag.endswith('service'):
                s_type_elem = find_tag(service, 'serviceType')
                if s_type_elem is not None and ('WANIPConnection' in s_type_elem.text or 'WANPPPConnection' in s_type_elem.text):
                    s_url_elem = find_tag(service, 'controlURL')
                    if s_url_elem is not None:
                        control_url = s_url_elem.text
                        service_type = s_type_elem.text
                        break
                        
        if not control_url:
            print("[UPnP] Could not find WANIPConnection or WANPPPConnection control URL.")
            return False
            
        parsed_loc = urllib.parse.urlparse(location_url)
        if control_url.startswith('http'):
            full_control_url = control_url
        else:
            base_url = f"{parsed_loc.scheme}://{parsed_loc.netloc}"
            full_control_url = urllib.parse.urljoin(base_url, control_url)
            
        print(f"[UPnP] Found control URL: {full_control_url} (Service: {service_type})")
        
        local_ip = get_local_ip()
        
        soap_body = f\"\"\"<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" 
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:AddPortMapping xmlns:u="{service_type}">
      <NewRemoteHost></NewRemoteHost>
      <NewExternalPort>{internal_port}</NewExternalPort>
      <NewProtocol>TCP</NewProtocol>
      <NewInternalPort>{internal_port}</NewInternalPort>
      <NewInternalClient>{local_ip}</NewInternalClient>
      <NewEnabled>1</NewEnabled>
      <NewPortMappingDescription>RemoteDesktopP2P</NewPortMappingDescription>
      <NewLeaseDuration>0</NewLeaseDuration>
    </u:AddPortMapping>
  </s:Body>
</s:Envelope>\"\"\"

        headers = {
            'SOAPAction': f'"{service_type}#AddPortMapping"',
            'Content-Type': 'text/xml',
        }
        
        req = urllib.request.Request(full_control_url, data=soap_body.encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = response.read().decode('utf-8')
            if 'AddPortMappingResponse' in res_data:
                print(f"[UPnP] Automatically forwarded external port {internal_port} to local IP {local_ip}!")
                return True
                
    except Exception as e:
        print(f"[UPnP] Error configuring port mapping on router: {e}")
        
    return False
"""

print(f"Finding blocks to replace in app.py...")

# Regex for APP_KEY
app_key_pattern = re.compile(r"APP_KEY = \"q3tu0y7j\"\n")
content, n0 = app_key_pattern.subn("", content)

# Regex for TCP Frame Helper Functions (from `_socket_send_locks` to `recv_msg`)
tcp_pattern = re.compile(
    r"# TCP Frame Helper Functions.*?def recv_msg\(sock, password=None\):.*?        return b''\n",
    re.DOTALL
)
content, n1 = tcp_pattern.subn(
    "from network.crypto import get_crypto_key, encrypt_payload, decrypt_payload\\n"
    "from network.socket_utils import socket_passwords, APP_KEY, force_close_socket, send_msg, recv_msg, recv_exact\\n",
    content
)

# Regex for UPnP
upnp_pattern = re.compile(
    r"# Automatic UPnP Port Forwarding via SSDP and SOAP\ndef attempt_upnp_forward\(internal_port\):.*?    return False\n",
    re.DOTALL
)
content, n2 = upnp_pattern.subn(
    "from network.upnp import attempt_upnp_forward\\n",
    content
)

print(f"Replacements made: APP_KEY={n0}, TCP={n1}, UPNP={n2}")

if n1 == 1 and n2 == 1:
    os.makedirs("d:/Data/AG/remote_desktop/network", exist_ok=True)
    with open("d:/Data/AG/remote_desktop/network/__init__.py", "w", encoding="utf-8") as f:
        pass
    with open("d:/Data/AG/remote_desktop/network/crypto.py", "w", encoding="utf-8") as f:
        f.write(crypto_code)
    with open("d:/Data/AG/remote_desktop/network/socket_utils.py", "w", encoding="utf-8") as f:
        f.write(socket_utils_code)
    with open("d:/Data/AG/remote_desktop/network/upnp.py", "w", encoding="utf-8") as f:
        f.write(upnp_code)
        
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(content)
    print("Refactor successful!")
else:
    print("Error: Could not find all blocks to replace exactly. Regex might need tweaking.")
