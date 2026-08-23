import re

service_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(service_file, 'r', encoding='utf-8') as f:
    service_content = f.read()

# Add imports if missing
imports = """import android.view.View
import android.view.WindowManager
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.provider.Settings
import android.view.Gravity"""

for imp in imports.split('\n'):
    if imp not in service_content:
        service_content = service_content.replace('import android.content.Intent', f"{imp}\nimport android.content.Intent")

# Add overlay variables
if 'private var dummyOverlay: View?' not in service_content:
    class_pattern = re.compile(r'(class ScreenCaptureService : Service\(\) \{)')
    vars_code = """\1
    private var dummyOverlay: View? = null
    private var windowManager: WindowManager? = null
    private var toggleColor = false

    fun triggerScreenUpdate() {
        dummyOverlay?.post {
            toggleColor = !toggleColor
            dummyOverlay?.setBackgroundColor(if (toggleColor) Color.argb(1, 0, 0, 0) else Color.TRANSPARENT)
            dummyOverlay?.invalidate()
        }
    }
    
    private fun initDummyOverlay() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                return
            }
            windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
            dummyOverlay = View(this).apply {
                setBackgroundColor(Color.TRANSPARENT)
            }
            val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                WindowManager.LayoutParams.TYPE_SYSTEM_ALERT // For Android 5.x
            }
            val params = WindowManager.LayoutParams(
                1, 1,
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or 
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT
            )
            params.gravity = Gravity.TOP or Gravity.START
            windowManager?.addView(dummyOverlay, params)
        } catch (e: Exception) {
            Log.e("ScreenCaptureService", "Failed to init dummy overlay: ${e.message}")
        }
    }"""
    service_content = class_pattern.sub(vars_code, service_content)

# Add initDummyOverlay to onCreate
if 'initDummyOverlay()' not in service_content:
    oncreate_pattern = re.compile(r'(override fun onCreate\(\) \{.*?super\.onCreate\(\))', re.DOTALL)
    service_content = oncreate_pattern.sub(r'\1\n        initDummyOverlay()', service_content)

# Remove dummy overlay in onDestroy
if 'dummyOverlay?.let { windowManager?.removeView(it) }' not in service_content:
    ondestroy_pattern = re.compile(r'(override fun onDestroy\(\) \{.*?super\.onDestroy\(\))', re.DOTALL)
    service_content = ondestroy_pattern.sub(r'\1\n        try { dummyOverlay?.let { windowManager?.removeView(it) } } catch(e: Exception) {}', service_content)

with open(service_file, 'w', encoding='utf-8') as f:
    f.write(service_content)

# Update TcpStreamManager to call triggerScreenUpdate instead of surface=null hack
tcp_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\TcpStreamManager.kt'
with open(tcp_file, 'r', encoding='utf-8') as f:
    tcp_content = f.read()

force_pattern = re.compile(r'(fun forceRefresh\(\) \{.*?try \{.*?val isSamsung =.*?if \(isSamsung\) \{.*?\} else \{)(.*?)(\}\s*\} catch \(e: Exception\) \{)', re.DOTALL)
force_repl = r'\1\n                // Dùng Dummy Overlay để ép màn hình nháy 1 pixel, Android OS sẽ nhả frame ngay lập tức!\n                ScreenCaptureService.instance?.triggerScreenUpdate()\n                \3'
tcp_content = force_pattern.sub(force_repl, tcp_content)

with open(tcp_file, 'w', encoding='utf-8') as f:
    f.write(tcp_content)
