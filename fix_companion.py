file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('    companion object {\n', '    companion object {\n        fun triggerScreenUpdate() { instance?.triggerScreenUpdateInternal() }\n')

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)