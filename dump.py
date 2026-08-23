file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[:60]):
    print(f"{i+1:02d}: {line.rstrip()}")