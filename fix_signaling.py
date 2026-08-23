import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\SignalingClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_str = """                        val myLocalIps = getLocalIpAddress()
                        val myPort = 12346 // Port TCP server Android đang listen
                        sendAction("connect_accept", JSONObject().apply { 
                            put("target", fromHwid) 
                            put("local_ip", myLocalIps)
                            put("port", myPort)
                            put("local_port", myPort)
                        })
                    }"""

new_str = """                        val myLocalIps = getLocalIpAddress()
                        val myPort = 12346 // Port TCP server Android đang listen
                        
                        // DELAY GỬI CONNECT_ACCEPT ĐỂ ĐẢM BẢO ANDROID HOLE PUNCHER CHẠY TRƯỚC VÀ TẠO NAT MAPPING!
                        // Điều này ngăn Router B gửi RST làm chết PC1 Viewer.
                        thread {
                            Thread.sleep(1000)
                            sendAction("connect_accept", JSONObject().apply { 
                                put("target", fromHwid) 
                                put("local_ip", myLocalIps)
                                put("port", myPort)
                                put("local_port", myPort)
                            })
                        }
                    }"""

content = content.replace(old_str, new_str)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)