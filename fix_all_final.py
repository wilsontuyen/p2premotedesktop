import re

# 1. Update SignalingClient.kt
sig_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\SignalingClient.kt'
with open(sig_file, 'r', encoding='utf-8') as f:
    sig_content = f.read()

# Bind Signaling Socket to 12345
sig_bind_old = """                s = Socket()
                s.tcpNoDelay = true"""
sig_bind_new = """                s = Socket()
                s.reuseAddress = true
                try { s.bind(InetSocketAddress(12345)) } catch(e: Exception) {}
                s.tcpNoDelay = true"""
sig_content = sig_content.replace(sig_bind_old, sig_bind_new)

with open(sig_file, 'w', encoding='utf-8') as f:
    f.write(sig_content)

# 2. Update ScreenCaptureService.kt
sc_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(sc_file, 'r', encoding='utf-8') as f:
    sc_content = f.read()
sc_content = sc_content.replace('put("port", 12347)', 'put("port", 12345)')
sc_content = sc_content.replace('put("local_port", 12347)', 'put("local_port", 12345)')
with open(sc_file, 'w', encoding='utf-8') as f:
    f.write(sc_content)

# 3. Update DataTransferClient.kt
dt_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(dt_file, 'r', encoding='utf-8') as f:
    dt_content = f.read()

# Make startServerAndWait use port 12345 instead of 12346
dt_content = dt_content.replace('fun startServerAndWait(\n        context: Context, password: String, deviceId: String, port: Int = 12346', 'fun startServerAndWait(\n        context: Context, password: String, deviceId: String, port: Int = 12345')

# Host Hole Puncher
host_pattern = re.compile(r'(thread\(name = "HolePuncher"\) \{.*?System\.setProperty\("java\.net\.preferIPv4Stack", "true"\))(.*?)(// 2\.5: TCP Hole Punching)', re.DOTALL)
host_repl = r'''\1
                                // Chờ 2s giống hệt Windows để Viewer bên kia kịp start HolePuncher
                                Thread.sleep(2000)

                                if (keepPunching && isRunning && finalAccepted == null) {
                                    isPunching = true
                                    Log.d(TAG, "Initiating Hole Punch to $clientPublicIp:$clientPublicPort")
                                    try { serverSocket?.close() } catch (e: Exception) {}
                                    
                                    var punchedSocket: Socket? = null
                                    for (i in 1..10) {
                                        if (!keepPunching || !isRunning || finalAccepted != null) break
                                        var currentPs: Socket? = null
                                        try {
                                            val ps = Socket()
                                            currentPs = ps
                                            ps.reuseAddress = true
                                            
                                            var bound = false
                                            for(b in 1..5) {
                                                try {
                                                    ps.bind(InetSocketAddress(port))
                                                    bound = true
                                                    break
                                                } catch(e: Exception) {
                                                    Thread.sleep(100)
                                                }
                                            }
                                            if (!bound) {
                                                Log.e(TAG, "Failed to bind hole puncher to port $port")
                                                throw Exception("Bind timeout")
                                            }
                                            
                                            ps.connect(InetSocketAddress(clientPublicIp, clientPublicPort), 6000)
                                            punchedSocket = ps
                                            Log.d(TAG, "Hole Punch SUCCESS to $clientPublicIp:$clientPublicPort")
                                            break
                                        } catch (e: Exception) {
                                            try { currentPs?.close() } catch (ex: Exception) {}
                                            Thread.sleep(500) // Sleep 500ms on fail to match Windows
                                        }
                                    }
                                    
                                    if (punchedSocket != null) {
                                        finalAccepted = punchedSocket
                                    }
                                    isPunching = false
                                    
                                    // Re-bind serverSocket after hole punch if failed
                                    if (punchedSocket == null && isRunning && finalAccepted == null) {
                                        try {
                                            val newSs = ServerSocket()
                                            newSs.reuseAddress = true
                                            newSs.bind(InetSocketAddress(port))
                                            serverSocket = newSs
                                        } catch (e: Exception) {}
                                    }
                                }
                            }
                    }

                    \3'''
dt_content = host_pattern.sub(host_repl, dt_content)

# Viewer Hole Puncher
viewer_pattern = re.compile(r'(// 2\.5: TCP Hole Punching cho Viewer.*?val punchPort = )12347', re.DOTALL)
viewer_repl = r'\1 12345'
dt_content = viewer_pattern.sub(viewer_repl, dt_content)

with open(dt_file, 'w', encoding='utf-8') as f:
    f.write(dt_content)