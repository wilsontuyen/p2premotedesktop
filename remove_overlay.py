import re

file1 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file1, 'r', encoding='utf-8') as f:
    text1 = f.read()

# Remove imports
text1 = text1.replace('import android.view.View\n', '')
text1 = text1.replace('import android.view.WindowManager\n', '')
text1 = text1.replace('import android.graphics.Color\n', '')
text1 = text1.replace('import android.graphics.PixelFormat\n', '')
text1 = text1.replace('import android.os.Build\n', '')
text1 = text1.replace('import android.provider.Settings\n', '')
text1 = text1.replace('import android.view.Gravity\n', '')

# Remove variables
text1 = re.sub(r'    private var dummyOverlay: View\? = null\n    private var windowManager: WindowManager\? = null\n    private var toggleColor = false\n', '', text1)

# Remove initDummyOverlay function
text1 = re.sub(r'    private fun initDummyOverlay\(\) \{.*?\n    \}\n', '', text1, flags=re.DOTALL)

# Remove initDummyOverlay() call
text1 = text1.replace('        initDummyOverlay()\n', '')

# Remove companion object function
text1 = re.sub(r'    companion object \{\n        fun triggerScreenUpdate\(\) \{ instance\?\.triggerScreenUpdateInternal\(\) \}\n', '    companion object {\n', text1)

# Remove triggerScreenUpdateInternal
text1 = re.sub(r'    fun triggerScreenUpdateInternal\(\) \{.*?\n    \}\n\n', '', text1, flags=re.DOTALL)

# Remove onDestroy cleanup
text1 = re.sub(r'        try \{ dummyOverlay\?\.let \{ windowManager\?\.removeView\(it\) \} \} catch\(e: Exception\) \{\}\n', '', text1)

with open(file1, 'w', encoding='utf-8') as f:
    f.write(text1)


file2 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\TcpStreamManager.kt'
with open(file2, 'r', encoding='utf-8') as f:
    text2 = f.read()

force_logic = """    fun forceRefresh() {
        try {
            val surface = imageReader?.surface ?: return
            handler?.post {
                try {
                    virtualDisplay?.surface = null
                    virtualDisplay?.surface = surface
                    Log.d("TcpStreamManager", "Force refreshed VirtualDisplay surface via API")
                } catch (e: Exception) {
                    Log.e("TcpStreamManager", "forceRefresh inner error: ${e.message}")
                }
            }
        } catch (e: Exception) {
            Log.e("TcpStreamManager", "forceRefresh error: ${e.message}")
        }
    }"""
text2 = re.sub(r'    fun forceRefresh\(\) \{.*?\n    \}', force_logic, text2, flags=re.DOTALL)

with open(file2, 'w', encoding='utf-8') as f:
    f.write(text2)