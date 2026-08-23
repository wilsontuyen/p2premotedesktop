import re

# 1. Clean ScreenCaptureService.kt
file1 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file1, 'rb') as f:
    content1 = f.read()

# Remove BOM if exists
if content1.startswith(b'\xef\xbb\xbf'):
    content1 = content1[3:]

# Decode
text1 = content1.decode('utf-8')

# Remove any weird zero-width spaces or non-breaking spaces on empty lines before class ScreenCaptureService
text1 = re.sub(r'\n[ \t\r\xa0\u200b]+\nclass ScreenCaptureService', '\n\nclass ScreenCaptureService', text1)

with open(file1, 'w', encoding='utf-8') as f:
    f.write(text1)

# 2. Fix TcpStreamManager.kt
file2 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\TcpStreamManager.kt'
with open(file2, 'r', encoding='utf-8') as f:
    text2 = f.read()

text2 = text2.replace('ScreenCaptureService.instance?.triggerScreenUpdate()', 'ScreenCaptureService.triggerScreenUpdate()')

with open(file2, 'w', encoding='utf-8') as f:
    f.write(text2)