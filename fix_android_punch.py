import os

path = r"d:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("Thread.sleep(1000)", "Thread.sleep(200)")
content = content.replace("Thread.sleep(2000) // Đợi PC Client kết nối LAN xong", "Thread.sleep(300) // Đợi PC Client kết nối LAN xong")
content = content.replace("for (i in 1..20) {", "for (i in 1..40) {")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched successfully")
