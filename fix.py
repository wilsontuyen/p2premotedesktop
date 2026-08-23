import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\r\n', '\n')

content = re.sub(
    r'var keepPunching = true\s*val ss = ServerSocket\(\)',
    'var keepPunching = true\n                        var isPunching = false\n                        val ss = ServerSocket()',
    content
)

content = re.sub(
    r'while \(finalAccepted == null && isRunning\) \{\s*try \{\s*if \(serverSocket == null',
    '''while (finalAccepted == null && isRunning) {
                            try {
                                if (isPunching) {
                                    Thread.sleep(500)
                                    continue
                                }
                                if (serverSocket == null''',
    content
)

host_pattern = re.compile(r'(thread\(name = "HolePuncher"\) \{)(.*?)(// [^\n]*accept loop.*?try \{ Socket\(\)\.connect\(InetSocketAddress\("127\.0\.0\.1", port\)\) \} catch \(e: Exception\) \{\}\s*\})', re.DOTALL)
host_repl = r'''\1
                                System.setProperty("java.net.preferIPv4Stack", "true")
                                // BO THOI GIAN DOI 2S!
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
                                            try { ps.bind(InetSocketAddress(port)) } catch (e: Exception) {}
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
                                    \3'''
content = host_pattern.sub(host_repl, content)

viewer_pattern = re.compile(r'(// 3\. FALLBACK: N.*?u P2P th.*?t b.*?i, ch.*? d.*?ng xin Relay\s*if \(!connected\) \{)', re.DOTALL)
viewer_repl = r'''// 2.5: TCP Hole Punching cho Viewer
                    if (!connected && publicIp.isNotBlank() && port > 0) {
                        Log.d(TAG, "Initiating Viewer Hole Punch to $publicIp:$port")
                        System.setProperty("java.net.preferIPv4Stack", "true")
                        val punchPort = 12347
                        for (i in 1..10) {
                            if (connected) break
                            var currentPs: Socket? = null
                            try {
                                val ps = Socket()
                                currentPs = ps
                                ps.reuseAddress = true
                                try { ps.bind(InetSocketAddress(punchPort)) } catch (e: Exception) {}
                                ps.connect(InetSocketAddress(publicIp, port), 6000)
                                s = ps
                                connected = true
                                Log.d(TAG, "Viewer Hole Punch: SUCCESS to $publicIp:$port")
                                break
                            } catch (e: Exception) {
                                try { currentPs?.close() } catch (ex: Exception) {}
                                Thread.sleep(500)
                            }
                        }
                    }

                    \1'''
content = viewer_pattern.sub(viewer_repl, content)

content = re.sub(r'nextSocket\.connect\(InetSocketAddress\(target\.first, target\.second\), 3000\)', 'nextSocket.connect(InetSocketAddress(target.first, target.second), 1000)', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)