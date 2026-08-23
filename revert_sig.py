# Revert SignalingClient.kt to original state before my hacks
import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\SignalingClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the delay and punchPort logic
old_str = """                        val myPort = 12346 // Port TCP server Android đang listen
                        val punchPort = 12345 // Port RIÊNG BIỆT dùng cho Đục lỗ (tránh xung đột bind với serverSocket)
                        
                        // DELAY GỬI CONNECT_ACCEPT ĐỂ ĐẢM BẢO ANDROID HOLE PUNCHER CHẠY TRƯỚC VÀ TẠO NAT MAPPING!
                        thread {
                            Thread.sleep(1000)
                            sendAction("connect_accept", JSONObject().apply { 
                                put("target", fromHwid) 
                                put("local_ip", myLocalIps)
                                put("port", punchPort) // DÙNG PUNCH PORT!
                                put("local_port", punchPort)
                            })
                        }"""

new_str = """                        val myPort = 12345 // ĐỔI SANG 12345 GIỐNG PC!
                        sendAction("connect_accept", JSONObject().apply { 
                            put("target", fromHwid) 
                            put("local_ip", myLocalIps)
                            put("port", myPort)
                            put("local_port", myPort)
                        })"""

content = content.replace(old_str, new_str)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)