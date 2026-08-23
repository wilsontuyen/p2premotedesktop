import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the Host HolePuncher thread
old_host = """                            thread(name = "HolePuncher") {
                                System.setProperty("java.net.preferIPv4Stack", "true")
                                // BO THOI GIAN DOI 2S!
                                if (keepPunching && isRunning && finalAccepted == null) {
                                    isPunching = true
                                    Log.d(TAG, "Initiating Hole Punch to $clientPublicIp:$clientPublicPort")
                                    // KHA"NG ĐA"NG serverSocket NỮA! ĐỂ NÓ CHẠY BAONH THƯỜNG TRASN 12346!
                                    
                                    var punchedSocket: Socket? = null
                                    for (i in 1..10) {
                                        if (!keepPunching || !isRunning || finalAccepted != null) break
                                        var currentPs: Socket? = null
                                        try {
                                            val ps = Socket()
                                            currentPs = ps
                                            ps.reuseAddress = true
                                            val punchPort = 12345 // DATNG CỔNG RIASNG CHO ĐỤC LỖ
                                            ps.bind(InetSocketAddress(punchPort))
                                            Log.d(TAG, "Successfully bound HolePuncher to port $punchPort")
                                            ps.connect(InetSocketAddress(clientPublicIp, clientPublicPort), 6000)
                                            punchedSocket = ps
                                            Log.d(TAG, "Hole Punch SUCCESS to $clientPublicIp:$clientPublicPort")
                                            break
                                        } catch (e: Exception) {
                                            try { currentPs?.close() } catch (ex: Exception) {}
                                            Thread.sleep(100)
                                        }
                                    }
                                    
                                    if (punchedSocket != null) {
                                        finalAccepted = punchedSocket
                                    }
                                    isPunching = false
                                    // Đánh thức accept loop
                                    try { Socket().connect(InetSocketAddress("127.0.0.1", port)) } catch (e: Exception) {}
                                }
                            }"""

# Using regex because of encoding issues in comments!
host_pattern = re.compile(r'thread\(name = "HolePuncher"\) \{.*?try \{ Socket\(\)\.connect\(InetSocketAddress\("127\.0\.0\.1", port\)\) \} catch \(e: Exception\) \{\}\s*\}\s*\}', re.DOTALL)

new_host = """thread(name = "HolePuncher") {
                                System.setProperty("java.net.preferIPv4Stack", "true")
                                // Chờ 2s giống hệt Windows để Viewer bên kia kịp khởi động HolePuncher
                                Thread.sleep(2000)

                                if (keepPunching && isRunning && finalAccepted == null) {
                                    isPunching = true
                                    Log.d(TAG, "Initiating Hole Punch to $clientPublicIp:$clientPublicPort")
                                    // Đóng serverSocket tạm thời giống hệt Windows
                                    try { serverSocket?.close() } catch (e: Exception) {}
                                    
                                    var punchedSocket: Socket? = null
                                    for (i in 1..10) {
                                        if (!keepPunching || !isRunning || finalAccepted != null) break
                                        var currentPs: Socket? = null
                                        try {
                                            val ps = Socket()
                                            currentPs = ps
                                            ps.reuseAddress = true
                                            
                                            // Cố gắng bind vào cổng 12345 (Windows dùng 12345)
                                            var bound = false
                                            for(b in 1..5) {
                                                try {
                                                    ps.bind(InetSocketAddress(12345))
                                                    bound = true
                                                    break
                                                } catch(e: Exception) {
                                                    Thread.sleep(100)
                                                }
                                            }
                                            if (!bound) {
                                                Log.e(TAG, "Failed to bind hole puncher to port 12345")
                                                throw Exception("Bind timeout")
                                            }
                                            
                                            ps.connect(InetSocketAddress(clientPublicIp, clientPublicPort), 6000)
                                            punchedSocket = ps
                                            Log.d(TAG, "Hole Punch SUCCESS to $clientPublicIp:$clientPublicPort")
                                            break
                                        } catch (e: Exception) {
                                            try { currentPs?.close() } catch (ex: Exception) {}
                                            Thread.sleep(500) // Ngủ 500ms khi lỗi giống hệt Windows Viewer
                                        }
                                    }
                                    
                                    if (punchedSocket != null) {
                                        finalAccepted = punchedSocket
                                    }
                                    isPunching = false
                                    
                                    // Đánh thức accept loop
                                    try { Socket().connect(InetSocketAddress("127.0.0.1", port)) } catch (e: Exception) {}
                                }
                            }"""

content = host_pattern.sub(new_host, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)