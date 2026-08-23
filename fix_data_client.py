import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# DON'T CLOSE SERVER SOCKET
content = content.replace('try { serverSocket?.close() } catch (e: Exception) {}', '// KHÔNG ĐÓNG serverSocket NỮA! ĐỂ NÓ CHẠY BÌNH THƯỜNG TRÊN 12346!')

# BIND TO 12348 INSTEAD OF port (12346)
old_bind = """                                            val ps = Socket()
                                            currentPs = ps
                                            ps.reuseAddress = true
                                            ps.bind(InetSocketAddress(port))
                                            Log.d(TAG, "Successfully bound HolePuncher to port $port")"""

new_bind = """                                            val ps = Socket()
                                            currentPs = ps
                                            ps.reuseAddress = true
                                            val punchPort = 12348 // DÙNG CỔNG RIÊNG CHO ĐỤC LỖ
                                            ps.bind(InetSocketAddress(punchPort))
                                            Log.d(TAG, "Successfully bound HolePuncher to port $punchPort")"""
                                            
content = content.replace(old_bind, new_bind)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)