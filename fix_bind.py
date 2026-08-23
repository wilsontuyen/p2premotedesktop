import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Host HolePuncher bind
content = content.replace(
    'try { ps.bind(InetSocketAddress(port)) } catch (e: Exception) {}',
    'ps.bind(InetSocketAddress(port))\n                                            Log.d(TAG, "Successfully bound HolePuncher to port $port")'
)

# Fix 2: Viewer HolePuncher bind
content = content.replace(
    'try { ps.bind(InetSocketAddress(punchPort)) } catch (e: Exception) {}',
    'ps.bind(InetSocketAddress(punchPort))\n                                Log.d(TAG, "Successfully bound Viewer HolePuncher to port $punchPort")'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)