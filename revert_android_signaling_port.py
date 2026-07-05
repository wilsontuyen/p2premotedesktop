import os

path = r"d:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\SignalingClient.kt"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target_str = """                socket = Socket()
                socket?.reuseAddress = true
                try {
                    // Cố gắng bind vào port 12346 để giữ nguyên port public (cho TCP Hole Punching)
                    socket?.bind(InetSocketAddress(12346))
                } catch (e: Exception) {
                    android.util.Log.e(TAG, "Failed to bind signaling socket to 12346: ${e.message}")
                }
                socket?.connect(InetSocketAddress(ipv4, port), 10000)"""

replacement_str = """                socket = Socket()
                socket?.connect(InetSocketAddress(ipv4, port), 10000)"""

content = content.replace(target_str, replacement_str)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Reverted SignalingClient.kt")
