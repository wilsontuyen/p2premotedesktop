package com.example.p2pdroidremote

import com.google.crypto.tink.subtle.ChaCha20Poly1305
import android.content.Context
import android.graphics.Bitmap
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.DataInputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread

class DataTransferClient {
    private val TAG = "DataTransferClient"
    private var socket: Socket? = null
    private var serverSocket: ServerSocket? = null
    private var tinkCipher: ChaCha20Poly1305? = null
    private val sendCounter = AtomicLong(0)
    
    // For file upload (PC -> Android)
    private var currentFileOutputStream: java.io.FileOutputStream? = null
    
    private var lastMouseX: Float = 0f
    private var lastMouseY: Float = 0f
    private var pendingBbox: android.graphics.Rect? = null
    private var screenWidth: Int = 0
    private var screenHeight: Int = 0
    private var viewerWidth: Int = 0
    private var viewerHeight: Int = 0
    
    private var appContext: Context? = null
    private var isRunning = false
    private var fallbackCipher: ChaCha20Poly1305? = null

    init {
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            val keyBytes = digest.digest("q3tu0y7j".toByteArray(Charsets.UTF_8))
            fallbackCipher = ChaCha20Poly1305(keyBytes)
        } catch (e: Exception) {
            Log.e(TAG, "Fallback key init error: ${e.message}")
        }
    }

    fun closeSockets() {
        try {
            socket?.let { s ->
                if (!s.isClosed) {
                    try { s.shutdownInput() } catch (_: Exception) {}
                    try { s.shutdownOutput() } catch (_: Exception) {}
                    s.close()
                }
            }
        } catch (_: Exception) {}
        
        try {
            serverSocket?.let { ss ->
                if (!ss.isClosed) {
                    ss.close()
                }
            }
        } catch (_: Exception) {}

        socket = null
        serverSocket = null
        Log.d(TAG, "Sockets closed and cleared.")
    }

    fun stop() {
        isRunning = false
        closeSockets()
    }

    fun startServerAndWait(
        context: Context, password: String, deviceId: String, port: Int, 
        preEstablishedSocket: Socket? = null, 
        clientPublicIp: String? = null, clientPublicPort: Int = 0, clientLocalIps: String? = null,
        onConnected: () -> Unit, onDisconnected: (() -> Unit)? = null
    ) {
        this.appContext = context.applicationContext
        isRunning = true
        UPnPManager.openPortBackground(context, port)
        
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            val cleanPass = password.trim()
            Log.d(TAG, "Initializing Server Tink with password: [$cleanPass] (len: ${cleanPass.length})")
            val keyBytes = digest.digest(cleanPass.toByteArray(Charsets.UTF_8))
            
            tinkCipher = ChaCha20Poly1305(keyBytes)
            sendCounter.set(0)
        } catch (e: Exception) {
            Log.e(TAG, "Key derivation failed: ${e.message}")
            return
        }

        thread(name = "DataTransferServer") {
            while (isRunning) {
                try {
                    // Đảm bảo socket cũ đã đóng hoàn toàn
                    closeSockets()
                    
                    // Thêm delay lâu hơn để OS giải phóng port (đặc biệt khi có nhiều reconnect)
                    Thread.sleep(200)

                    val s = if (preEstablishedSocket != null) {
                        Log.d(TAG, "Using RELAY socket")
                        // Relay socket is one-shot
                        isRunning = false 
                        preEstablishedSocket
                    } else {
                        var finalAccepted: Socket? = null
                        var keepPunching = true
                        var isPunching = false
                        val ss = ServerSocket()
                        serverSocket = ss
                        ss.reuseAddress = true
                        try {
                            ss.bind(InetSocketAddress(port))
                        } catch (e: Exception) {
                            Log.e(TAG, "Bind failed on port $port: ${e.message}")
                            ss.close()
                            Thread.sleep(2000)
                            continue 
                        }
                        Log.d(TAG, "ID-Link Server started on port $port. Waiting for PC connection...")
                        
                        if (clientPublicIp != null && clientPublicPort > 0) {
                            thread(name = "HolePuncher") {
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
                                            
                                            // Cố gắng bind vào các cổng 12345, 12346, 12347...
                                            var bound = false
                                            for (testPort in 12345..12350) {
                                                for(b in 1..2) {
                                                    try {
                                                        ps.bind(InetSocketAddress(testPort))
                                                        bound = true
                                                        break
                                                    } catch(e: Exception) {
                                                        Thread.sleep(50)
                                                    }
                                                }
                                                if (bound) break
                                            }
                                            if (!bound) {
                                                Log.e(TAG, "Failed to bind hole puncher to any port 12345-12350")
                                                throw Exception("Bind timeout")
                                            }
                                            
                                            ps.connect(InetSocketAddress(clientPublicIp, clientPublicPort), 6000)
                                            punchedSocket = ps
                                            Log.d(TAG, "Hole Punch SUCCESS to $clientPublicIp:$clientPublicPort")
                                            break
                                        } catch (e: Exception) {
                                            try { currentPs?.close() } catch (ex: Exception) {}
                                            Thread.sleep(1500) // Ngủ 1500ms trên Android 5.x để xả TIME_WAIT
                                        }
                                    }
                                    
                                    if (punchedSocket != null) {
                                        finalAccepted = punchedSocket
                                    }
                                    isPunching = false
                                    
                                    // Đánh thức accept loop
                                    try { Socket().connect(InetSocketAddress("127.0.0.1", port)) } catch (e: Exception) {}
                                }
                            }
                        }
                        
                        while (finalAccepted == null && isRunning) {
                            try {
                                if (isPunching) {
                                    Thread.sleep(500)
                                    continue
                                }
                                if (serverSocket == null || serverSocket!!.isClosed) {
                                    val newSs = ServerSocket()
                                    newSs.reuseAddress = true
                                    try {
                                        newSs.bind(InetSocketAddress(port))
                                        serverSocket = newSs
                                        Log.d(TAG, "Re-bound ServerSocket on port $port")
                                    } catch (e: Exception) {
                                        Thread.sleep(500)
                                        continue
                                    }
                                }
                                val accepted = serverSocket?.accept()
                                if (accepted != null) {
                                    if (accepted.inetAddress.hostAddress == "127.0.0.1") {
                                        accepted.close() // Bỏ qua dummy trigger
                                    } else {
                                        finalAccepted = accepted
                                    }
                                }
                            } catch (e: Exception) {
                                Thread.sleep(100)
                            }
                        }
                        
                        keepPunching = false
                        if (finalAccepted == null) break
                        
                        Log.d(TAG, "PC connected from: ${finalAccepted.inetAddress.hostAddress}")
                        finalAccepted
                    }
                    
                    s.tcpNoDelay = true
                    val dis = DataInputStream(s.getInputStream())
                    
                    Log.d(TAG, "Socket connected. Waiting for PC handshake...")
                    val handshakeJson = try { 
                        receiveEncryptedJson(dis) 
                    } catch (e: Exception) {
                        Log.e(TAG, "Handshake failed: ${e.message}")
                        s.close()
                        if (!isRunning) break
                        continue // Retry for direct connections
                    }
                    
                    val receivedPassword = handshakeJson.optString("password").trim()
                    val expectedPassword = password.trim()
                    
                    if (receivedPassword == expectedPassword) {
                        Log.d(TAG, "Handshake successful! PC: ${handshakeJson.optString("computer_name")}")
                        
                        val windowManager = ContextCompat.getSystemService(context, WindowManager::class.java)!!
                        val metrics = DisplayMetrics()
                        @Suppress("DEPRECATION")
                        windowManager.defaultDisplay.getRealMetrics(metrics)
                        
                        screenWidth = metrics.widthPixels
                        screenHeight = metrics.heightPixels

                        val response = JSONObject().apply {
                            put("status", "ok")
                            put("width", screenWidth)
                            put("height", screenHeight)
                            put("computer_name", android.os.Build.MODEL)
                            put("is_android", true)
                        }
                        sendEncryptedData(s, response.toString().toByteArray(Charsets.UTF_8))
                        
                        runBandwidthTest(s, dis)
                        
                        socket = s
                        onConnected()
                        sendCachedFrameNow(s)
                        startFrameSender(s)
                        receiveLoop(s, dis)
                        onDisconnected?.invoke()
                        // After receiveLoop finishes, we might want to restart listener
                        Log.d(TAG, "Session ended, restarting listener...")
                    } else {
                        Log.e(TAG, "Handshake failed: Wrong password")
                        s.close()
                    }
                    serverSocket?.close()
                    serverSocket = null
                } catch (e: Exception) {
                    if (isRunning) {
                        Log.e(TAG, "Server error: ${e.message}, retrying in 5s...")
                        Thread.sleep(5000)
                    }
                }
            }
        }
    }

    private fun runBandwidthTest(s: Socket, dis: DataInputStream) {
        try {
            s.soTimeout = 5000 
            for (round in 1..2) {
                while (true) {
                    val msg = receiveEncryptedJson(dis)
                    val action = msg.optString("action")
                    if (action == "speed_test_ping") {
                        sendEncryptedData(s, JSONObject().apply { put("action", "speed_test_pong") }.toString().toByteArray(Charsets.UTF_8))
                    } else if (action == "speed_test_bw_req") {
                        val totalToSend = 1572864
                        sendEncryptedData(s, JSONObject().apply { 
                            put("action", "speed_test_bw_start")
                            put("size", totalToSend) 
                        }.toString().toByteArray(Charsets.UTF_8))

                        var sentTotal = 0
                        val dummy = ByteArray(16384)
                        val os = s.getOutputStream()
                        while (sentTotal < totalToSend) {
                            val toSend = minOf(dummy.size, totalToSend - sentTotal)
                            os.write(dummy, 0, toSend)
                            sentTotal += toSend
                        }
                        os.flush()
                        break 
                    } else if (action == "speed_test_result") return else break
                }
            }
        } catch (e: Exception) {} finally {
            try { s.soTimeout = 0 } catch (e: Exception) {}
        }
    }

    private fun runBandwidthTestClient(s: Socket, dis: DataInputStream) {
        try {
            Log.d(TAG, "Bandwidth Test Client: Starting...")
            s.soTimeout = 8000
            
            for (round in 1..2) {
                Log.d(TAG, "Bandwidth Test Client: Round $round starting...")
                for (i in 1..3) {
                    val ping = JSONObject().apply { put("action", "speed_test_ping") }
                    sendEncryptedData(s, ping.toString().toByteArray(Charsets.UTF_8))
                    receiveEncryptedJson(dis)
                }

                val req = JSONObject().apply { put("action", "speed_test_bw_req") }
                sendEncryptedData(s, req.toString().toByteArray(Charsets.UTF_8))
                
                val startMsg = receiveEncryptedJson(dis)
                if (startMsg.optString("action") == "speed_test_bw_start") {
                    val dummySize = startMsg.optLong("size", 1572864L)
                    Log.d(TAG, "Bandwidth Test Client Round $round: Consuming $dummySize bytes...")
                    
                    var bytesRead = 0L
                    val buffer = ByteArray(16384)
                    while (bytesRead < dummySize) {
                        val toRead = Math.min(buffer.size.toLong(), dummySize - bytesRead).toInt()
                        val read = dis.read(buffer, 0, toRead)
                        if (read == -1) break
                        bytesRead += read
                    }
                    Log.d(TAG, "Bandwidth Test Client: Round $round finished ($bytesRead bytes)")
                }
            }

            val result = JSONObject().apply {
                put("action", "speed_test_result")
                put("net_class", "high")
                put("bandwidth", 100.0)
            }
            sendEncryptedData(s, result.toString().toByteArray(Charsets.UTF_8))
            Log.d(TAG, "Bandwidth Test: Finished.")
            
        } catch (e: Exception) {
            Log.w(TAG, "Bandwidth test error: ${e.message}")
        } finally {
            try { s.soTimeout = 0 } catch (e: Exception) {}
        }
    }

    private fun receiveEncryptedJson(dis: DataInputStream): JSONObject {
        val length = dis.readInt()
        if (length <= 0 || length > 10 * 1024 * 1024) throw Exception("Invalid packet length: $length")
        
        val payload = ByteArray(length)
        dis.readFully(payload)
        
        if (payload.isNotEmpty() && payload[0] == '{'.code.toByte()) {
            return JSONObject(String(payload, Charsets.UTF_8))
        }

        if (length < 28) throw Exception("Packet too short for crypto")
        
        val decrypted = decrypt(payload)
        if (decrypted == null) throw Exception("Decryption failed")

        return JSONObject(String(decrypted, Charsets.UTF_8))
    }

    private fun decrypt(fullPayload: ByteArray): ByteArray? {
        if (fullPayload.size < 28) return null
        
        // Thử giải mã với khóa chính
        tinkCipher?.let { cipher ->
            try {
                return cipher.decrypt(fullPayload, null)
            } catch (_: Exception) {}
        }

        // Thử giải mã với khóa dự phòng
        fallbackCipher?.let { cipher ->
            try {
                return cipher.decrypt(fullPayload, null)
            } catch (_: Exception) {}
        }

        // Log lỗi nếu cả hai đều thất bại
        Log.e(TAG, "Decryption failed for payload of length ${fullPayload.size}")
        return null
    }

    private fun encrypt(plaintext: ByteArray): ByteArray? {
        val cipher = tinkCipher ?: return null
        return try {
            // Tink's encrypt(plaintext, associatedData) returns [Nonce(12)][Plaintext][Tag(16)]
            cipher.encrypt(plaintext, null)
        } catch (e: Exception) { 
            Log.e(TAG, "Encryption error: ${e.message}")
            null 
        }
    }

    // [FIX] startFrameSender dùng getFrameJpeg() thread-safe thay vì getCurrentBitmap()
    // để tránh crash khi ImageReader recycle bitmap giữa chừng.
    // Đây là luồng gửi frame DUY NHẤT - TcpStreamManager chỉ capture, không gửi.
    // [FIX] startFrameSender dùng waitForNextFrame thread-safe để tránh gửi liên tục khung hình tĩnh gây quá tải mạng và CPU.
    private fun sendCachedFrameNow(s: Socket) {
        val cached = TcpStreamManager.instance?.peekLastGoodFrame() ?: return
        sendEncryptedData(s, cached.second)
        Log.d(TAG, "Sent cached screen immediately id=${cached.first} size=${cached.second.size}")
    }

    private fun startFrameSender(s: Socket) {
        thread(name = "FrameSender") {
            try {
                var lastSeenId = 0L
                val cached = TcpStreamManager.instance?.peekLastGoodFrame()
                if (cached != null) {
                    lastSeenId = cached.first
                    sendEncryptedData(s, cached.second)
                    Log.d(TAG, "FrameSender: reused cached frame id=${cached.first}")
                } else {
                    Log.d(TAG, "FrameSender: no cache, waiting for first capture...")
                    val initialFrame = TcpStreamManager.instance?.waitForNextFrame(-1L, 800L)
                    if (initialFrame != null) {
                        lastSeenId = initialFrame.first
                        sendEncryptedData(s, initialFrame.second)
                    } else {
                        TcpStreamManager.instance?.forceRefresh()
                    }
                }
                
                // Giới hạn số lần forceRefresh liên tiếp để tránh vòng lặp chết
                // (đặc biệt trên Samsung khi recreate VirtualDisplay tốn tài nguyên)
                var consecutiveRefreshCount = 0
                val MAX_CONSECUTIVE_REFRESH = 3
                
                while (s.isConnected && !s.isClosed) {
                    val currentSocket = socket
                    if (currentSocket == null || currentSocket.isClosed) break

                    // Wait for next frame (timeout 2000ms to allow checking socket status)
                    val frameInfo = TcpStreamManager.instance?.waitForNextFrame(lastSeenId, 2000L)
                    if (frameInfo != null) {
                        lastSeenId = frameInfo.first
                        val jpegBytes = frameInfo.second
                        sendEncryptedData(s, jpegBytes)
                        consecutiveRefreshCount = 0  // Reset counter khi cA3 frame thAnh cA'ng
                    } else {
                        // HEARTBEAT RESEND: Nu Viewer b l> frame 'u tiAn (do mng hoc render li),
                        // chAAng ta gi li frame c sau mi 2 giAy cho d mAn hAnh khA'ng 'i
                        val cachedJpeg = TcpStreamManager.instance?.peekLastGoodFrame()?.second
                            ?: TcpStreamManager.instance?.getFrameJpeg()
                        if (cachedJpeg != null) {
                            Log.d(TAG, "No new frame. Resending cached frame (Heartbeat)...")
                            sendEncryptedData(s, cachedJpeg)
                        } else {
                            consecutiveRefreshCount++
                            if (consecutiveRefreshCount <= MAX_CONSECUTIVE_REFRESH) {
                                // Fix for black screen on lock/unlock: force a refresh if the frame is stuck
                                Log.d(TAG, "No frame, forceRefresh attempt $consecutiveRefreshCount/$MAX_CONSECUTIVE_REFRESH")
                                TcpStreamManager.instance?.forceRefresh()
                            } else {
                                if (consecutiveRefreshCount == MAX_CONSECUTIVE_REFRESH + 1) {
                                    Log.w(TAG, "Max forceRefresh reached. Waiting for frame without refresh...")
                                }
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "FrameSender error: ${e.message}")
            }
        }
    }

    fun sendActionSync(data: JSONObject) {
        val s = socket ?: return
        sendEncryptedData(s, data.toString().toByteArray(Charsets.UTF_8))
    }

    private fun receiveLoop(s: Socket, dis: DataInputStream) {
        try {
            while (true) {
                val length = dis.readInt()
                if (length <= 0) break
                if (length > 10 * 1024 * 1024) continue
                
                val payload = ByteArray(length)
                dis.readFully(payload)
                
                if (payload.isNotEmpty() && payload[0] == '{'.code.toByte()) {
                    handlePeerMessage(String(payload, Charsets.UTF_8))
                    continue
                }

                val decrypted = decrypt(payload)
                if (decrypted != null) {
                    val text = String(decrypted, Charsets.UTF_8)
                    if (text.startsWith("{")) {
                        if (text.length > 1000) Log.d(TAG, "Large message received: ${text.take(50)}...")
                        handlePeerMessage(text)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "receiveLoop error: ${e.message}")
        } finally { stop() }
    }

    fun sendEncryptedData(s: Socket, data: ByteArray) {
        try {
            if (s.isClosed || !s.isConnected) return
            
            val fullPayload = encrypt(data) ?: return
            
            val totalSize = fullPayload.size
            val buffer = ByteBuffer.allocate(4 + totalSize).order(ByteOrder.BIG_ENDIAN)
            buffer.putInt(totalSize)
            buffer.put(fullPayload)

            synchronized(this) {
                val os = s.getOutputStream()
                os.write(buffer.array())
                os.flush()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Send error: ${e.message}")
            if (e is java.net.SocketException || e.message?.contains("EPIPE") == true || e.message?.contains("reset") == true) {
                stop()
            }
        }
    }

    private fun handlePeerMessage(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type", json.optString("action"))
            when (type) {
                "ping" -> sendActionSync(JSONObject().apply { put("type", "pong") })
                "resize_viewer" -> {
                    viewerWidth = json.optInt("w", 0)
                    viewerHeight = json.optInt("h", 0)
                }
                "quality_mode" -> {
                    TcpStreamManager.instance?.setQualityMode(json.optString("mode", "quality"))
                }
                "mouse_move" -> {
                    lastMouseX = json.optDouble("x", 0.0).toFloat()
                    lastMouseY = json.optDouble("y", 0.0).toFloat()
                }
                "mouse_click" -> {
                    if (!json.optBoolean("pressed", false)) {
                        val cx = json.optDouble("x", lastMouseX.toDouble()).toFloat()
                        val cy = json.optDouble("y", lastMouseY.toDouble()).toFloat()
                        val service = RemoteControlService.instance
                        if (service != null) {
                            service.click(cx, cy)
                        } else {
                            // Show Toast on main thread to warn user
                            appContext?.let { ctx ->
                                android.os.Handler(android.os.Looper.getMainLooper()).post {
                                    android.widget.Toast.makeText(ctx, "LỖI: Quyền Trợ Năng bị kẹt! Vui lòng vào Cài đặt Tắt và Bật lại P2P Remote!", android.widget.Toast.LENGTH_LONG).show()
                                }
                            }
                        }
                    }
                }
                "mouse_swipe" -> {
                    val x1 = json.optDouble("x1", 0.0).toFloat()
                    val y1 = json.optDouble("y1", 0.0).toFloat()
                    val x2 = json.optDouble("x2", 0.0).toFloat()
                    val y2 = json.optDouble("y2", 0.0).toFloat()
                    val duration = json.optLong("duration", 300L)
                    RemoteControlService.instance?.swipe(x1, y1, x2, y2, duration)
                }
                "mouse_swipe_path" -> {
                    val pathArray = json.optJSONArray("path")
                    val duration = json.optLong("duration", 300L)
                    if (pathArray != null && pathArray.length() > 0) {
                        RemoteControlService.instance?.swipePath(pathArray, duration)
                    }
                }
                "mouse_scroll" -> RemoteControlService.instance?.scroll(json.optInt("dy", 0))
                "request_full_frame" -> TcpStreamManager.instance?.triggerFullFrame()
                "request_cached_frame" -> {
                    val sock = socket
                    val jpeg = TcpStreamManager.instance?.peekLastGoodFrame()?.second
                        ?: TcpStreamManager.instance?.getFrameJpeg()
                    if (sock != null && jpeg != null) {
                        sendEncryptedData(sock, jpeg)
                        Log.d(TAG, "Sent cached frame on request (${jpeg.size} bytes)")
                    }
                }
                "key_event" -> if (json.optBoolean("pressed", true)) {
                    RemoteControlService.instance?.handleKey(json.optString("key", ""), true)
                }
                "paste_text" -> {
                    val text = json.optString("text", "")
                    if (text.isNotEmpty()) {
                        RemoteControlService.instance?.typeText(text)
                    }
                }
                "request_list_dir" -> {
                    val path = json.optString("path", "/sdcard")
                    try {
                        val dir = java.io.File(path)
                        val items = org.json.JSONArray()
                        var files = dir.listFiles()
                        if (files == null) {
                            if (path == "/") {
                                val knownPaths = listOf("/sdcard", "/storage", "/system", "/data", "/mnt", "/dev", "/proc")
                                val fallbackList = mutableListOf<java.io.File>()
                                for (p in knownPaths) {
                                    val f = java.io.File(p)
                                    if (f.exists()) fallbackList.add(f)
                                }
                                files = fallbackList.toTypedArray()
                            } else if (path == "/storage") {
                                val knownPaths = listOf("/storage/emulated", "/storage/self")
                                val fallbackList = mutableListOf<java.io.File>()
                                for (p in knownPaths) {
                                    val f = java.io.File(p)
                                    if (f.exists()) fallbackList.add(f)
                                }
                                files = fallbackList.toTypedArray()
                            }
                        }
                        
                        files?.forEach { file ->
                            val item = JSONObject()
                            item.put("name", file.name)
                            item.put("is_dir", file.isDirectory)
                            item.put("size", file.length())
                            items.put(item)
                        }
                        val res = JSONObject()
                        res.put("type", "list_dir_result")
                        res.put("path", path)
                        res.put("items", items)
                        sendActionSync(res)
                    } catch (e: Exception) { Log.e(TAG, "List dir error: ${e.message}") }
                }
                "request_file_download" -> {
                    val path = json.optString("path")
                    thread(name = "FileDownloader") {
                        try {
                            val file = java.io.File(path)
                            if (file.exists() && file.isFile) {
                                val start = JSONObject()
                                start.put("type", "file_start")
                                start.put("name", file.name)
                                start.put("size", file.length())
                                sendActionSync(start)
                                
                                val fis = java.io.FileInputStream(file)
                                val buffer = ByteArray(65536)
                                var bytesRead: Int
                                while (fis.read(buffer).also { bytesRead = it } != -1) {
                                    val chunkObj = JSONObject()
                                    chunkObj.put("type", "file_chunk")
                                    chunkObj.put("name", file.name)
                                    chunkObj.put("data", android.util.Base64.encodeToString(buffer, 0, bytesRead, android.util.Base64.NO_WRAP))
                                    sendActionSync(chunkObj)
                                    Thread.sleep(2)
                                }
                                fis.close()
                                
                                val endObj = JSONObject()
                                endObj.put("type", "file_end")
                                endObj.put("name", file.name)
                                sendActionSync(endObj)
                            }
                        } catch (e: Exception) { Log.e(TAG, "File Download error: ${e.message}") }
                    }
                }
                "request_download_batch" -> {
                    val paths = json.optJSONArray("paths") ?: return
                    thread(name = "BatchDownloader") {
                        try {
                            for (i in 0 until paths.length()) {
                                val path = paths.optString(i)
                                val rootFile = java.io.File(path)
                                if (!rootFile.exists()) continue
                                
                                val baseName = rootFile.name
                                val filesToProcess = if (rootFile.isFile) listOf(rootFile) else rootFile.walkTopDown().filter { it.isFile }.toList()
                                
                                for (file in filesToProcess) {
                                    val relPath = if (rootFile.isDirectory) {
                                        baseName + "/" + file.toRelativeString(rootFile).replace("\\\\", "/")
                                    } else {
                                        file.name
                                    }
                                    
                                    val start = JSONObject()
                                    start.put("type", "file_start")
                                    start.put("name", relPath)
                                    start.put("size", file.length())
                                    sendActionSync(start)
                                    
                                    val fis = java.io.FileInputStream(file)
                                    val buffer = ByteArray(65536)
                                    var bytesRead: Int
                                    while (fis.read(buffer).also { bytesRead = it } != -1) {
                                        val chunkObj = JSONObject()
                                        chunkObj.put("type", "file_chunk")
                                        chunkObj.put("name", relPath)
                                        chunkObj.put("data", android.util.Base64.encodeToString(buffer, 0, bytesRead, android.util.Base64.NO_WRAP))
                                        sendActionSync(chunkObj)
                                        Thread.sleep(2)
                                    }
                                    fis.close()
                                    
                                    val endObj = JSONObject()
                                    endObj.put("type", "file_end")
                                    endObj.put("name", relPath)
                                    sendActionSync(endObj)
                                    Thread.sleep(50)
                                }
                            }
                            
                            val batchEndObj = JSONObject()
                            batchEndObj.put("type", "batch_end")
                            sendActionSync(batchEndObj)
                            
                        } catch (e: Exception) { Log.e(TAG, "Batch Download error: ${e.message}") }
                    }
                }
                "request_delete_item" -> {
                    val path = json.optString("path")
                    val res = JSONObject().apply { put("type", "delete_item_result") }
                    try {
                        val file = java.io.File(path)
                        val success = if (file.isDirectory) file.deleteRecursively() else file.delete()
                        res.put("success", success)
                        if (!success) res.put("error", "Delete failed")
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_rename_item" -> {
                    val oldPath = json.optString("old_path")
                    val newName = json.optString("new_name")
                    val res = JSONObject().apply { put("type", "rename_item_result") }
                    try {
                        val oldFile = java.io.File(oldPath)
                        val newFile = java.io.File(oldFile.parent, newName)
                        val success = oldFile.renameTo(newFile)
                        res.put("success", success)
                        if (!success) res.put("error", "Rename failed")
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_create_folder" -> {
                    val parentPath = json.optString("parent_path")
                    val folderName = json.optString("folder_name")
                    val res = JSONObject().apply { put("type", "create_folder_result") }
                    try {
                        val newFolder = java.io.File(parentPath, folderName)
                        val success = newFolder.mkdirs() || newFolder.exists()
                        res.put("success", success)
                        if (!success) res.put("error", "Create folder failed")
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_open_file" -> {
                    val path = json.optString("path")
                    val res = JSONObject().apply { put("type", "open_file_result") }
                    try {
                        val file = java.io.File(path)
                        if (file.exists()) {
                            try {
                                val method = android.os.StrictMode::class.java.getMethod("disableDeathOnFileUriExposure")
                                method.invoke(null)
                            } catch (e: Exception) {}
                            
                            val intent = android.content.Intent(android.content.Intent.ACTION_VIEW)
                            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                            
                            var type = "*/*"
                            val extension = android.webkit.MimeTypeMap.getFileExtensionFromUrl(file.name)
                            if (extension != null) {
                                val mime = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension.lowercase())
                                if (mime != null) type = mime
                            }
                            intent.setDataAndType(android.net.Uri.fromFile(file), type)
                            appContext?.startActivity(intent)
                            res.put("success", true)
                        } else {
                            res.put("success", false)
                            res.put("error", "File not found")
                        }
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_read_text_file" -> {
                    val path = json.optString("path")
                    val res = JSONObject().apply { 
                        put("type", "read_text_file_result")
                        put("path", path)
                    }
                    try {
                        val file = java.io.File(path)
                        if (file.exists() && file.isFile) {
                            if (file.length() > 5 * 1024 * 1024) {
                                res.put("success", false)
                                res.put("error", "File quá lớn (> 5MB)")
                            } else {
                                val content = file.readText(Charsets.UTF_8)
                                res.put("success", true)
                                res.put("content", content)
                            }
                        } else {
                            res.put("success", false)
                            res.put("error", "File not found")
                        }
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_write_text_file" -> {
                    val path = json.optString("path")
                    val content = json.optString("content")
                    val res = JSONObject().apply { 
                        put("type", "write_text_file_result")
                        put("path", path)
                    }
                    try {
                        val file = java.io.File(path)
                        file.writeText(content, Charsets.UTF_8)
                        res.put("success", true)
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "request_get_properties" -> {
                    val path = json.optString("path")
                    val res = JSONObject().apply { put("type", "get_properties_result") }
                    try {
                        val file = java.io.File(path)
                        if (file.exists()) {
                            val name = file.name
                            val location = file.parent ?: ""
                            val isDir = file.isDirectory
                            val modifiedTime = try {
                                val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault())
                                sdf.format(java.util.Date(file.lastModified()))
                            } catch (e: Exception) { "" }

                            res.put("success", true)
                            res.put("name", name)
                            res.put("is_dir", isDir)
                            res.put("location", location)
                            res.put("modified_time", modifiedTime)

                            if (isDir) {
                                var totalSize = 0L
                                var fileCount = 0
                                var folderCount = 0
                                try {
                                    file.walkTopDown().forEach { f ->
                                        if (f == file) return@forEach
                                        if (f.isDirectory) {
                                            folderCount++
                                        } else {
                                            fileCount++
                                            totalSize += f.length()
                                        }
                                    }
                                } catch (e: Exception) {}
                                res.put("size", totalSize)
                                res.put("file_count", fileCount)
                                res.put("folder_count", folderCount)
                            } else {
                                res.put("size", file.length())
                            }
                        } else {
                            res.put("success", false)
                            res.put("error", "Path not found")
                        }
                    } catch (e: Exception) {
                        res.put("success", false)
                        res.put("error", e.message)
                    }
                    sendActionSync(res)
                }
                "file_start" -> {
                    val targetDir = json.optString("target_dir", "/sdcard/Download")
                    val name = json.optString("name")
                    try {
                        val dir = java.io.File(targetDir)
                        if (!dir.exists()) dir.mkdirs()
                        val file = java.io.File(dir, name)
                        currentFileOutputStream = java.io.FileOutputStream(file)
                    } catch (e: Exception) { Log.e(TAG, "file_start error", e) }
                }
                "file_chunk" -> {
                    val b64 = json.optString("data")
                    if (b64.isNotEmpty() && currentFileOutputStream != null) {
                        try {
                            val bytes = android.util.Base64.decode(b64, android.util.Base64.DEFAULT)
                            currentFileOutputStream?.write(bytes)
                        } catch (e: Exception) { Log.e(TAG, "file_chunk error", e) }
                    }
                }
                "file_end" -> {
                    try {
                        currentFileOutputStream?.close()
                        currentFileOutputStream = null
                    } catch (e: Exception) {}
                }
                "check_domain", "clipboard_text" -> { /* Ignore for now but keep connection alive */ }
            }
        } catch (e: Exception) {}
    }

    fun sendAction(action: String, data: String, meta: JSONObject? = null) {
        val s = socket ?: return
        thread {
            try {
                val json = meta ?: JSONObject()
                json.put("action", action)
                json.put("data", data)
                sendEncryptedData(s, json.toString().toByteArray(Charsets.UTF_8))
            } catch (e: Exception) {}
        }
    }

    fun connectToPartner(
        context: Context, publicIp: String, localIps: String?, 
        port: Int, localPort: Int, password: String, deviceId: String,
        isRelay: Boolean = false, sessionId: String? = null,
        onResolutionChange: ((Int, Int) -> Unit)? = null,
        onError: ((String) -> Unit)? = null,
        onFrameReceived: (ByteArray, android.graphics.Rect?) -> Unit
    ) {
        this.appContext = context.applicationContext
        thread {
            try {
                var s = Socket()
                var connected = false
                var currentSessionId = sessionId

                if (isRelay && sessionId != null) {
                    // 1. Trường hợp được Server báo có Relay (Incoming hoặc Fallback đã xong)
                    s.connect(InetSocketAddress(publicIp, port), 10000)
                    s.getOutputStream().write("RELAY_CLIENT:$sessionId\n".toByteArray(Charsets.UTF_8))
                    s.getOutputStream().flush()
                    connected = true
                } else {
                    // 2. Thử P2P Direct
                    val allIps = mutableListOf<Pair<String, Int>>()
                    localIps?.split(",")?.forEach { if (it.isNotBlank()) allIps.add(Pair(it, localPort)) }
                    if (publicIp.isNotBlank()) allIps.add(Pair(publicIp, port))
                    for (target in allIps) {
                        try {
                            Log.d(TAG, "Attempting connection to ${target.first}:${target.second}...")
                            val nextSocket = Socket()
                            nextSocket.connect(InetSocketAddress(target.first, target.second), 1000) 
                            s = nextSocket
                            connected = true
                            break
                        } catch (e: Exception) {}
                    }

                    // 2.5: TCP Hole Punching cho Viewer (Đã tối ưu cho Android 5.x)
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
                                
                                // Bind vào cổng cố định, nếu bận thì tịnh tiến lên
                                var bound = false
                                for (p in 12345..12350) {
                                    try {
                                        ps.bind(InetSocketAddress(p))
                                        bound = true
                                        break
                                    } catch (e: Exception) {}
                                }
                                if (!bound) throw Exception("Bind timeout Viewer")
                                
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

                    // 3. FALLBACK: Nếu P2P thất bại, chủ động xin Relay
                    if (!connected) {
                        val targetId = (context as? ViewerActivity)?.intent?.getStringExtra("TARGET_ID")?.replace(" ", "")?.trim()
                        if (targetId != null) {
                            Log.d(TAG, "P2P Failed. Initiating active relay request for $targetId...")
                            val timestamp = System.currentTimeMillis() / 1000
                            val newSessionId = "session_${deviceId}_${targetId}_${timestamp}"
                            currentSessionId = newSessionId
                            
                            // Gửi yêu cầu qua Signaling
                            ScreenCaptureService.instance?.requestRelay(targetId, newSessionId)
                            
                            // Mở socket mới tới Signaling Server (port 8765)
                            val signalingHost = ScreenCaptureService.instance?.getSignalingHost() ?: publicIp
                            val signalingPort = ScreenCaptureService.instance?.getSignalingPort() ?: 8765
                            
                            val relaySocket = Socket()
                            relaySocket.connect(InetSocketAddress(signalingHost, signalingPort), 5000)
                            relaySocket.tcpNoDelay = true
                            
                            // Gửi Header RAW định danh
                            val header = "RELAY_CLIENT:$newSessionId\n"
                            relaySocket.getOutputStream().write(header.toByteArray(Charsets.UTF_8))
                            relaySocket.getOutputStream().flush()
                            
                            s = relaySocket
                            connected = true
                            Log.d(TAG, "Relay tunnel established via $signalingHost")
                        }
                    }
                }

                if (!connected) throw Exception("All connection attempts failed")
                
                s.tcpNoDelay = true
                socket = s
                
                val digest = MessageDigest.getInstance("SHA-256")
                val cleanPass = password.trim()
                Log.d("CryptoTest", "Viewer password encrypting length: ${cleanPass.length}, value: [$cleanPass]")
                tinkCipher = ChaCha20Poly1305(digest.digest(cleanPass.toByteArray(Charsets.UTF_8)))
                sendCounter.set(0)
                
                val dis = DataInputStream(s.getInputStream())
                
                Log.d(TAG, "Viewer: Handshaking...")
                val handshake = JSONObject().apply {
                    put("password", cleanPass)
                    put("client_id", deviceId)
                    put("computer_name", android.os.Build.MODEL)
                }
                sendEncryptedData(s, handshake.toString().toByteArray(Charsets.UTF_8))
                
                val response = receiveEncryptedJson(dis)
                val status = response.optString("status")
                if (status == "ok") {
                    Log.d(TAG, "Viewer: Handshake successful!")
                    runBandwidthTestClient(s, dis)

                    // Khởi động luồng Heartbeat để tránh PC ngắt kết nối sau 10 giây
                    thread(name = "ViewerHeartbeat") {
                        try {
                            while (s.isConnected && !s.isClosed) {
                                Thread.sleep(2000)
                                val heartbeat = JSONObject().apply { put("type", "ping") }
                                sendEncryptedData(s, heartbeat.toString().toByteArray(Charsets.UTF_8))
                            }
                        } catch (e: Exception) {
                            Log.d(TAG, "ViewerHeartbeat stopped")
                        }
                    }

                    Log.d(TAG, "Viewer: Main loop starting...")
                    while (s.isConnected && !s.isClosed) {
                        val length = dis.readInt()
                        if (length <= 0) break
                        if (length > 10 * 1024 * 1024) throw Exception("Packet too large: $length")
                        
                        val payload = ByteArray(length)
                        dis.readFully(payload)
                        
                        if (payload.isNotEmpty() && payload[0] == '{'.code.toByte()) {
                            try {
                                val text = String(payload, Charsets.UTF_8)
                                val json = JSONObject(text)
                                val b64 = json.optString("data", json.optString("image"))
                                if (b64.isNotEmpty()) {
                                    val imageBytes = android.util.Base64.decode(b64, android.util.Base64.DEFAULT)
                                    onFrameReceived(imageBytes, pendingBbox)
                                    pendingBbox = null
                                }
                            } catch (e: Exception) {}
                            continue
                        }

                        var decrypted = decrypt(payload)
                        if (decrypted == null) {
                            decrypted = try { fallbackCipher?.decrypt(payload, null) } catch (e: Exception) { null }
                        }
                        
                        if (decrypted != null) {
                            if (decrypted.isNotEmpty() && decrypted[0] == '{'.code.toByte()) {
                                try {
                                    val text = String(decrypted, Charsets.UTF_8)
                                    val json = JSONObject(text)
                                    
                                    val evType = json.optString("type")
                                    if (evType == "resolution_change") {
                                        val w = json.optInt("w")
                                        val h = json.optInt("h")
                                        if (w > 0 && h > 0) {
                                            onResolutionChange?.invoke(w, h)
                                        }
                                        continue
                                    }
                                    
                                    if (evType == "partial_frame" || json.has("bbox")) {
                                        val bboxArr = json.optJSONArray("bbox")
                                        if (bboxArr != null && bboxArr.length() == 4) {
                                            pendingBbox = android.graphics.Rect(
                                                bboxArr.getInt(0),
                                                bboxArr.getInt(1),
                                                bboxArr.getInt(2),
                                                bboxArr.getInt(3)
                                            )
                                        }
                                    } else {
                                        pendingBbox = null // Full frame
                                    }

                                    val b64 = json.optString("data", json.optString("image"))
                                    if (b64.isNotEmpty()) {
                                        val imageBytes = android.util.Base64.decode(b64, android.util.Base64.DEFAULT)
                                        onFrameReceived(imageBytes, pendingBbox)
                                        pendingBbox = null
                                    }
                                } catch (e: Exception) {}
                            } else {
                                onFrameReceived(decrypted, pendingBbox)
                                pendingBbox = null
                            }
                        }
                    }
                } else if (status == "error") {
                    val msg = response.optString("message", "Unknown error from PC")
                    android.os.Handler(android.os.Looper.getMainLooper()).post {
                        android.widget.Toast.makeText(context, "PC Error: $msg", android.widget.Toast.LENGTH_LONG).show()
                    }
                    onError?.invoke(msg)
                    throw Exception(msg)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Viewer Error: ${e.message}")
                e.printStackTrace()
            } finally { stop() }
        }
    }
}
