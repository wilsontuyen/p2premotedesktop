file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('val initialTimeout = if (isSamsungTablet) 5000L else 2000L', 'val initialTimeout = if (isSamsungTablet) 5000L else 1000L')

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)