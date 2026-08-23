import re

file_path = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('val punchPort = 12348', 'val punchPort = 12345')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
    
file_path2 = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\SignalingClient.kt'
with open(file_path2, 'r', encoding='utf-8') as f:
    content2 = f.read()

content2 = content2.replace('val punchPort = 12348', 'val punchPort = 12345')

with open(file_path2, 'w', encoding='utf-8') as f:
    f.write(content2)