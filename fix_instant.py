import re

# 1. Fix TcpStreamManager.kt
file1 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\TcpStreamManager.kt'
with open(file1, 'r', encoding='utf-8') as f:
    text1 = f.read()

wait_logic = """    fun waitForNextFrame(lastSeenId: Long, timeoutMs: Long): Pair<Long, ByteArray>? {
        synchronized(bitmapLock) {
            val endTime = System.currentTimeMillis() + timeoutMs
            while (lastJpegBytes == null || lastFrameId <= lastSeenId) {
                val waitTime = endTime - System.currentTimeMillis()
                if (waitTime <= 0) return null
                bitmapLock.wait(waitTime)
            }
            if (lastJpegBytes != null) {
                return Pair(lastFrameId, lastJpegBytes!!)
            }
            return null
        }
    }"""
text1 = re.sub(r'fun waitForNextFrame\(lastSeenId: Long, timeoutMs: Long\): Pair<Long, ByteArray>\? \{.*?\n    \}', wait_logic, text1, flags=re.DOTALL)

with open(file1, 'w', encoding='utf-8') as f:
    f.write(text1)

# 2. Fix DataTransferClient.kt
file2 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file2, 'r', encoding='utf-8') as f:
    text2 = f.read()

# Trigger refresh before waiting
text2 = text2.replace('val initialTimeout = if (isSamsungTablet) 5000L else 1000L', 'TcpStreamManager.instance?.forceRefresh()\n                val initialTimeout = if (isSamsungTablet) 5000L else 1000L')

with open(file2, 'w', encoding='utf-8') as f:
    f.write(text2)