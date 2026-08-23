import re

dt_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(dt_file, 'r', encoding='utf-8') as f:
    dt_content = f.read()

viewer_pattern = re.compile(r'(// 3\. FALLBACK:.*?if \(!connected\) \{)', re.DOTALL)
viewer_repl = r'''// 2.5: TCP Hole Punching cho Viewer (Đã tối ưu cho Android 5.x)
                    if (!connected && publicIp.isNotBlank() && port > 0) {
                        Log.d(TAG, "Initiating Viewer Hole Punch to $publicIp:$port")
                        System.setProperty("java.net.preferIPv4Stack", "true")
                        val punchPort = 12345
                        
                        for (i in 1..8) { // Giảm xuống 8 lần nhưng tăng thời gian nghỉ
                            if (connected) break
                            var currentPs: Socket? = null
                            try {
                                val ps = Socket()
                                currentPs = ps
                                
                                // Quan trọng trên Android 5.x: Bật reuse address trước khi bind
                                ps.reuseAddress = true
                                ps.soTimeout = 4000 // Timeout đọc/ghi socket
                                
                                // Bind vào cổng cố định
                                ps.bind(InetSocketAddress(punchPort))
                                
                                // Tiến hành kết nối tới PC1
                                ps.connect(InetSocketAddress(publicIp, port), 4000)
                                
                                s = ps
                                connected = true
                                Log.d(TAG, "Viewer Hole Punch: SUCCESS to $publicIp:$port on attempt $i")
                                break
                            } catch (e: Exception) {
                                // Đảm bảo đóng socket cũ triệt để để giải phóng PORT trên Linux kernel cũ
                                try {
                                    currentPs?.close()
                                } catch (ex: Exception) {}
                                
                                // Android 5.x cần thời gian đủ lâu (1.5 giây - 2 giây) để kernel giải phóng trạng thái TIME_WAIT của cổng 12345
                                Thread.sleep(1500) 
                            }
                        }
                    }

                    \1'''

dt_content = viewer_pattern.sub(viewer_repl, dt_content)

with open(dt_file, 'w', encoding='utf-8') as f:
    f.write(dt_content)