import re

file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports
imports = """import android.view.View
import android.view.WindowManager
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.provider.Settings
import android.view.Gravity
import java.net.NetworkInterface"""
content = content.replace('import android.content.Intent', f"{imports}\nimport android.content.Intent")

# 2. Add System.setProperty("java.net.preferIPv4Stack", "true")
content = content.replace('super.onCreate()\n        instance = this', 'super.onCreate()\n        System.setProperty("java.net.preferIPv4Stack", "true")\n        instance = this')

# 3. Add getLocalIpAddress
local_ip_func = """    private fun getLocalIpAddress(): String {
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
}"""
content = content.replace('}\n', f"\n{local_ip_func}\n", 1) # Only replace the LAST brace. Wait, regex is safer.
content = re.sub(r'\}\s*$', f"{local_ip_func}\n", content)


# 4. Modify connect_request
connect_req = """        if (::signalingClient.isInitialized) {
            val localIps = getLocalIpAddress()
            val data = JSONObject().apply {
                put("target", targetId)
                put("port", 12345)
                put("local_ip", localIps)
                put("local_port", 12345)
            }
            signalingClient.sendAction("connect_request", data)"""
content = re.sub(r'if \(::signalingClient\.isInitialized\) \{.*?signalingClient\.sendAction\("connect_request", data\)', connect_req, content, flags=re.DOTALL)


# 5. Add Dummy Overlay Logic
dummy_vars = """class ScreenCaptureService : Service() {
    private var dummyOverlay: View? = null
    private var windowManager: WindowManager? = null
    private var toggleColor = false

    private fun initDummyOverlay() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) return
            windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
            dummyOverlay = View(this).apply { setBackgroundColor(Color.TRANSPARENT) }
            val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
            val params = WindowManager.LayoutParams(1, 1, type, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL, PixelFormat.TRANSLUCENT)
            params.gravity = Gravity.TOP or Gravity.START
            windowManager?.addView(dummyOverlay, params)
        } catch (e: Exception) { Log.e("ScreenCaptureService", "Failed to init dummy overlay: ${e.message}") }
    }
"""
content = content.replace('class ScreenCaptureService : Service() {', dummy_vars)

content = content.replace('super.onCreate()\n        System.setProperty', 'super.onCreate()\n        initDummyOverlay()\n        System.setProperty')

# Add to companion object
content = content.replace('    companion object {\n        var instance', '    companion object {\n        fun triggerScreenUpdate() { instance?.triggerScreenUpdateInternal() }\n        var instance')

content = content.replace('    private lateinit var signalingClient', '    fun triggerScreenUpdateInternal() {\n        dummyOverlay?.post {\n            toggleColor = !toggleColor\n            dummyOverlay?.setBackgroundColor(if (toggleColor) Color.argb(1, 0, 0, 0) else Color.TRANSPARENT)\n            dummyOverlay?.invalidate()\n        }\n    }\n\n    private lateinit var signalingClient')

content = content.replace('super.onDestroy()', 'super.onDestroy()\n        try { dummyOverlay?.let { windowManager?.removeView(it) } } catch(e: Exception) {}')


with open(file, 'w', encoding='utf-8') as f:
    f.write(content)