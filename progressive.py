import re

file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file, 'r', encoding='utf-8') as f:
    text = f.read()

progressive_logic = """                Log.d(TAG, "FrameSender: Initializing fast progressive retries...")
                var initialFrame = TcpStreamManager.instance?.waitForNextFrame(-1L, 100L)
                if (initialFrame == null) {
                    Log.d(TAG, "Fast retry 1 (100ms)")
                    TcpStreamManager.instance?.forceRefresh()
                    initialFrame = TcpStreamManager.instance?.waitForNextFrame(-1L, 250L)
                    if (initialFrame == null) {
                        Log.d(TAG, "Fast retry 2 (350ms)")
                        TcpStreamManager.instance?.forceRefresh()
                        initialFrame = TcpStreamManager.instance?.waitForNextFrame(-1L, 400L)
                        if (initialFrame == null) {
                            Log.d(TAG, "Fast retry 3 (750ms)")
                            TcpStreamManager.instance?.forceRefresh()
                            initialFrame = TcpStreamManager.instance?.waitForNextFrame(-1L, 500L)
                        }
                    }
                }"""

text = re.sub(r'                val initialTimeout = if \(isSamsungTablet\) 5000L else 1000L.*?Log\.w\(TAG, "Still no frame after forceRefresh\. Continuing anyway\.\.\."\)\n                    \}\n                \}', progressive_logic, text, flags=re.DOTALL)

with open(file, 'w', encoding='utf-8') as f:
    f.write(text)

file2 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\TcpStreamManager.kt'
with open(file2, 'r', encoding='utf-8') as f:
    text2 = f.read()

# Add samsung check back
samsung_logic = """    fun forceRefresh() {
        try {
            val isSamsung = android.os.Build.MANUFACTURER.equals("samsung", ignoreCase = true)
            if (isSamsung) {
                Log.d("TcpStreamManager", "Samsung: Skipped forceRefresh to prevent VirtualDisplay crash")
                return
            }
            val surface = imageReader?.surface ?: return"""
text2 = text2.replace('    fun forceRefresh() {\n        try {\n            val surface = imageReader?.surface ?: return', samsung_logic)

with open(file2, 'w', encoding='utf-8') as f:
    f.write(text2)