file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the first companion object block
content = content.replace('    companion object {\n        fun triggerScreenUpdate() {\n            instance?.triggerScreenUpdateInternal()\n        }\n    }\n\n', '')

# Find the second one and add the function
content = content.replace('    companion object {', '    companion object {\n        fun triggerScreenUpdate() {\n            instance?.triggerScreenUpdateInternal()\n        }')

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)