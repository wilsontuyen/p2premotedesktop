package com.example.p2pdroidremote

import android.app.*
import java.net.NetworkInterface
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import androidx.compose.runtime.mutableStateOf
import org.json.JSONObject

class ScreenCaptureService : Service() {



    private lateinit var signalingClient: SignalingClient
    private var dataTransferClients = mutableListOf<DataTransferClient>()
    private lateinit var tcpStreamManager: TcpStreamManager
    private lateinit var lanDiscovery: LanDiscovery
    private var currentPassword = ""

    companion object {
        const val NOTIFICATION_ID = 1
        const val CHANNEL_ID = "ScreenCaptureChannel"
        var isRunning = mutableStateOf(false)
        var isSignalingConnected = mutableStateOf(false)
        var lastSignalingError = mutableStateOf("")
        var instance: ScreenCaptureService? = null
        var targetPartnerPassword = ""
        var targetPartnerId = ""
    
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
        } catch (_: Exception) {}
        return ips.joinToString(",")
    }
}

    override fun onCreate() {
        super.onCreate()
        System.setProperty("java.net.preferIPv4Stack", "true")
        instance = this
        isRunning.value = true
        createNotificationChannel()
        
        signalingClient = SignalingClient(object : SignalingClient.SignalingListener {
            override fun onConnected() {
                isSignalingConnected.value = true
                lastSignalingError.value = ""
            }
            override fun onDisconnected(reason: String) {
                isSignalingConnected.value = false
                lastSignalingError.value = reason
                signalingClient.isDataConnected = false
                
                // Hiển thị thông báo lỗi cho người dùng
                android.widget.Toast.makeText(this@ScreenCaptureService, "Signaling Error: $reason", android.widget.Toast.LENGTH_LONG).show()
            }
            override fun onPeerReady(publicIp: String, publicPort: Int, localIps: String, localPort: Int, relaySocket: java.net.Socket?, sessionId: String?) {
                val prefs = PreferenceManager(this@ScreenCaptureService)
                val deviceId = prefs.getDeviceId()
                
                Log.d("ScreenCaptureService", "Peer Ready. Port: $localPort, Relay: ${relaySocket != null}, Session: $sessionId")
                
                if (targetPartnerPassword.isNotEmpty()) {
                    // TRƯỜNG HỢP BẠN LÀ NGƯỜI ĐIỀU KHIỂN (VIEWER)
                    signalingClient.isDataConnected = true
                    val intent = Intent(this@ScreenCaptureService, ViewerActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        putExtra("TARGET_ID", targetPartnerId) 
                        putExtra("IP", publicIp)
                        putExtra("LOCAL_IPS", localIps) 
                        putExtra("PORT", publicPort)
                        putExtra("LOCAL_PORT", localPort)
                        putExtra("PASSWORD", targetPartnerPassword)
                        putExtra("IS_RELAY", relaySocket != null || publicIp == "relay" || sessionId != null)
                        putExtra("SESSION_ID", sessionId)
                    }
                    startActivity(intent)
                    targetPartnerPassword = "" // Reset sau khi dùng
                } else {
                    // TRƯỜNG HỢP BẠN LÀ NGƯỜI BỊ ĐIỀU KHIỂN (HOST)
                    val newClient = DataTransferClient()
                    dataTransferClients.add(newClient)
                    newClient.startServerAndWait(
                        this@ScreenCaptureService, currentPassword, deviceId, localPort, relaySocket,
                        publicIp, publicPort, localIps,
                        onConnected = {
                            signalingClient.isDataConnected = true
                        },
                        onDisconnected = {
                            dataTransferClients.remove(newClient)
                            if (dataTransferClients.isEmpty()) {
                                signalingClient.isDataConnected = false
                            }
                        }
                    )
                }
            }
        })
        
        lanDiscovery = LanDiscovery()
        tcpStreamManager = TcpStreamManager(this)
    }

    fun requestConnection(targetId: String) {
        Log.d("ScreenCaptureService", "Sending connect_request to $targetId")
                if (::signalingClient.isInitialized) {
            val localIps = getLocalIpAddress()
            val data = JSONObject().apply {
                put("target", targetId)
                put("port", 12345)
                put("local_ip", localIps)
                put("local_port", 12345)
            }
            signalingClient.sendAction("connect_request", data)
        } else {
            Log.e("ScreenCaptureService", "Signaling client NOT INITIALIZED")
        }
    }

    fun requestRelay(targetId: String, sessionId: String) {
        Log.d("ScreenCaptureService", "Sending relay_request to $targetId with session $sessionId")
        if (::signalingClient.isInitialized) {
            val data = JSONObject().apply {
                put("target", targetId)
                put("session_id", sessionId)
            }
            signalingClient.sendAction("relay_request", data)
        }
    }

    fun setDataConnected(connected: Boolean) {
        if (::signalingClient.isInitialized) {
            signalingClient.isDataConnected = connected
        }
    }

    fun getSignalingHost(): String? = if (::signalingClient.isInitialized) signalingClient.getLastHost() else null
    fun getSignalingPort(): Int = if (::signalingClient.isInitialized) signalingClient.getLastPort() else 8765

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val resultData: Intent? = intent?.let {
            IntentCompat.getParcelableExtra(it, "RESULT_DATA", Intent::class.java)
        }
        val deviceId = intent?.getStringExtra("DEVICE_ID") ?: ""
        val password = intent?.getStringExtra("PASSWORD") ?: ""
        
        if (password.isNotEmpty()) {
            currentPassword = password
        }

        val prefs = PreferenceManager(this)
        
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("P2PDroid Remote Host")
            .setContentText("Waiting for connection...")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
        startForeground(NOTIFICATION_ID, notification)

        // Kết nối Signaling
        if (deviceId.isNotEmpty()) {
            signalingClient.connect(prefs.serverHost, prefs.serverPort, deviceId)
            lanDiscovery.startListening(deviceId, 12346)
        }

        if (resultData != null) {
            tcpStreamManager.startStreaming(resultData)
        }

        return START_STICKY
    }

    private fun createNotificationChannel() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID, "Screen Capture Channel", NotificationManager.IMPORTANCE_LOW
            )
            val manager = ContextCompat.getSystemService(this, NotificationManager::class.java)!!
            manager.createNotificationChannel(serviceChannel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        isRunning.value = false
        isSignalingConnected.value = false
        lastSignalingError.value = ""
        tcpStreamManager.stopStreaming()
        dataTransferClients.forEach { it.stop() }
        dataTransferClients.clear()
        instance = null
        super.onDestroy()
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
        } catch (_: Exception) {}
        return ips.joinToString(",")
    }
}
