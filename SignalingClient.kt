package com.example.p2pdroidremote

import android.os.Handler
import android.os.Looper
import android.util.Log
import com.google.crypto.tink.subtle.ChaCha20Poly1305
import org.json.JSONObject
import java.io.DataInputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Timer
import java.util.TimerTask
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread

class SignalingClient(private val listener: SignalingListener) {
    companion object {
        private const val TAG = "SignalingClient"
    }
    private var socket: Socket? = null
    private val handler = Handler(Looper.getMainLooper())
    
    private var tinkCipher: ChaCha20Poly1305? = null
    private val sendCounter = AtomicLong(0)
    
    private var isConnected = false
    private val reconnectHandler = Handler(Looper.getMainLooper())
    private var pingTimer: Timer? = null
    
    var isDataConnected = false
    
    private var lastHost: String? = null
    private var lastPort: Int = 8765
    private var lastDeviceId: String? = null

    interface SignalingListener {
        fun onConnected()
        fun onDisconnected(reason: String)
        fun onPeerReady(publicIp: String, publicPort: Int, localIps: String, localPort: Int, relaySocket: Socket? = null, sessionId: String? = null)
    }

    fun getLastHost(): String? = lastHost
    fun getLastPort(): Int = lastPort

    fun connect(host: String, port: Int, deviceId: String) {
        this.lastHost = host
        this.lastPort = port
        this.lastDeviceId = deviceId
        this.sendCounter.set(0)

        try {
            val digest = MessageDigest.getInstance("SHA-256")
            val keyBytes = digest.digest("q3tu0y7j".toByteArray())
            tinkCipher = ChaCha20Poly1305(keyBytes)
            Log.d(TAG, "Tink ChaCha20Poly1305 initialized successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Tink init failed: ${e.message}")
        }

        thread {
            var errorReason = "Connection closed"
            try {
                val addresses = InetAddress.getAllByName(host)
                val ipv4 = addresses.firstOrNull { it.address.size == 4 } ?: addresses[0]
                
                socket = Socket()
                socket?.connect(InetSocketAddress(ipv4, port), 10000)
                socket?.tcpNoDelay = true

                val dis = DataInputStream(socket!!.getInputStream())

                // 1. Gửi bản tin Register (Sử dụng APP_KEY tĩnh)
                val regData = JSONObject().apply { 
                    put("action", "register")
                    put("hwid", deviceId) 
                }
                sendActionSync(regData)

                isConnected = true
                handler.post { listener.onConnected() }
                
                startPingTimer()

                while (true) {
                    Log.d(TAG, "Waiting for message length...")
                    val length = try { dis.readInt() } catch (e: java.io.EOFException) {
                        Log.w(TAG, "Server closed connection (EOF)")
                        break
                    }
                    Log.d(TAG, "Reading message of length: $length")
                    if (length <= 0 || length > 1024 * 1024) { // Bảo vệ nếu length quá lớn
                        Log.e(TAG, "Invalid message length: $length")
                        break
                    }
                    
                    val fullPayload = ByteArray(length)
                    dis.readFully(fullPayload)
                    Log.d(TAG, "Message payload read fully")

                    if (fullPayload.size > 12) {
                        val decrypted = decrypt(fullPayload)
                        if (decrypted != null) {
                            handleMessage(String(decrypted, Charsets.UTF_8))
                        } else {
                            Log.e(TAG, "Failed to decrypt message")
                        }
                    } else {
                        Log.e(TAG, "Payload too short: ${fullPayload.size}")
                    }
                }
            } catch (e: Exception) {
                errorReason = "${e.javaClass.simpleName}: ${e.message}"
                Log.e(TAG, "Signaling Error: $errorReason")
            } finally {
                stopPingTimer()
                isConnected = false
                handler.post { listener.onDisconnected(errorReason) }
                try { socket?.close() } catch (_: Exception) {}
                scheduleReconnect()
            }
        }
    }

    private fun encrypt(plaintext: ByteArray): ByteArray? {
        val cipher = tinkCipher ?: return null
        return try {
            cipher.encrypt(plaintext, null)
        } catch (e: Exception) {
            Log.e(TAG, "Tink encrypt error: ${e.message}")
            null
        }
    }

    private fun decrypt(ciphertextWithNonce: ByteArray): ByteArray? {
        val cipher = tinkCipher ?: return null
        return try {
            // Tink's decrypt(ciphertext, associatedData) expects the nonce to be prepended to the ciphertext.
            cipher.decrypt(ciphertextWithNonce, null)
        } catch (e: Exception) {
            Log.e(TAG, "Tink decrypt error: ${e.message}")
            null
        }
    }

    private fun getAvailablePort(startPort: Int = 12345, endPort: Int = 12350): Int {
        for (port in startPort..endPort) {
            try {
                val ss = java.net.ServerSocket(port)
                ss.close()
                return port
            } catch (e: Exception) {}
        }
        return startPort
    }

    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            val action = json.optString("action")
            
            // Chỉ log các message quan quan trọng, tránh spam incoming_request/ping/pong
            if (action != "incoming_request" && action != "pong" && action != "ping") {
                Log.d(TAG, "Signaling Msg: $text")
            }

            when {
                (action == "incoming_request") || (action == "peer_info") || (action == "connect_request") || (action == "request_accepted") -> {
                    val publicIp = json.optString("public_ip", json.optString("ip"))
                    val publicPort = json.optInt("public_port", json.optInt("port", 12345))
                    val localIps = json.optString("local_ip")
                    var assignedLocalPort = json.optInt("local_port", 12345)
                    val fromHwid = json.optString("from_hwid")

                    if (action == "incoming_request" && fromHwid.isNotEmpty()) {
                        Log.d(TAG, "Accepting incoming request from $fromHwid")
                        assignedLocalPort = getAvailablePort(12345, 12350)
                        val myLocalIps = getLocalIpAddress()
                        sendAction("connect_accept", JSONObject().apply { 
                            put("target", fromHwid) 
                            put("local_ip", myLocalIps)
                            put("port", assignedLocalPort)
                            put("local_port", assignedLocalPort)
                        })
                    }
                    
                    Log.d(TAG, "Executing onPeerReady for P2P/PeerInfo/Accepted on port $assignedLocalPort")
                    listener.onPeerReady(publicIp, publicPort, localIps, assignedLocalPort, null, null)
                    
                }
                action == "relay_request" -> {
                    val sessionId = json.optString("session_id")
                    Log.d(TAG, "Relay request received, session: $sessionId")
                    
                    thread {
                        try {
                            val relaySocket = Socket()
                            relaySocket.connect(InetSocketAddress(lastHost, lastPort), 5000)
                            relaySocket.tcpNoDelay = true
                            
                            val header = "RELAY_HOST:$sessionId\n"
                            relaySocket.getOutputStream().write(header.toByteArray(Charsets.UTF_8))
                            relaySocket.getOutputStream().flush()
                            
                            Log.d(TAG, "Connected as RELAY_HOST. Executing onPeerReady")
                            handler.post {
                                listener.onPeerReady("relay", 0, "relay", 0, relaySocket, sessionId)
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "Relay connection failed: ${e.message}")
                        }
                    }
                }
                action == "relay_client_request" -> {
                    val sessionId = json.optString("session_id")
                    Log.d(TAG, "Relay client request received, session: $sessionId")
                    listener.onPeerReady(lastHost ?: "", lastPort, "relay", 0, null, sessionId)
                }
                action == "error" -> {
                    val msg = json.optString("message", "Unknown error")
                    handler.post {
                        listener.onDisconnected(msg)
                    }
                }
            }
        } catch (e: Exception) {}
    }

    private fun sendActionSync(data: JSONObject) {
        try {
            val jsonStr = data.toString()
            Log.d(TAG, "Sending JSON: $jsonStr")
            val plaintext = jsonStr.toByteArray(Charsets.UTF_8)

            // Tink's ChaCha20Poly1305.encrypt generates a random 12-byte nonce 
            // and prepends it to the ciphertext automatically.
            // This results in [Nonce(12)][Ciphertext][Tag(16)]
            val fullPayload = encrypt(plaintext)
            if (fullPayload == null) {
                Log.e(TAG, "Encryption failed for $jsonStr")
                return
            }
            
            val totalPayloadSize = fullPayload.size
            val buffer = ByteBuffer.allocate(4 + totalPayloadSize).order(ByteOrder.BIG_ENDIAN)
            buffer.putInt(totalPayloadSize)
            buffer.put(fullPayload)

            synchronized(this) {
                socket?.getOutputStream()?.write(buffer.array())
                socket?.getOutputStream()?.flush()
                Log.d(TAG, "Sent $totalPayloadSize bytes to server")
            }
        } catch (e: Exception) {
            Log.e(TAG, "sendActionSync error: ${e.message}")
        }
    }

    fun sendAction(action: String, data: JSONObject = JSONObject()) {
        data.put("action", action)
        thread { sendActionSync(data) }
    }

    private fun startPingTimer() {
        stopPingTimer()
        pingTimer = Timer()
        pingTimer?.schedule(object : TimerTask() {
            override fun run() { if (isConnected) sendAction("ping") }
        }, 10000, 10000) // Tăng tần suất ping lên 10s để giữ kết nối Relay
    }

    private fun stopPingTimer() {
        pingTimer?.cancel()
        pingTimer = null
    }

    private fun scheduleReconnect() {
        reconnectHandler.removeCallbacksAndMessages(null)
        reconnectHandler.postDelayed({
            if (!isConnected && lastHost != null) {
                connect(lastHost!!, lastPort, lastDeviceId!!)
            }
        }, 5000)
    }

    private fun getLocalIpAddress(): String {
        val ips = mutableListOf<String>()
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (!addr.isLoopbackAddress && addr.address.size == 4) {
                        addr.hostAddress?.let { ips.add(it) }
                    }
                }
            }
        } catch (e: Exception) {}
        return ips.joinToString(",")
    }
}
