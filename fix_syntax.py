file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('    private var dummyOverlay: View? = null', 'class ScreenCaptureService : Service() {\n    private var dummyOverlay: View? = null')

# Also fix the initDummyOverlay Context issue: getSystemService(Context.WINDOW_SERVICE)
content = content.replace('getSystemService(Context.WINDOW_SERVICE)', 'getSystemService(WINDOW_SERVICE)')

# Also fix Settings.canDrawOverlays(this) which requires Context
content = content.replace('Settings.canDrawOverlays(this)', 'Settings.canDrawOverlays(this@ScreenCaptureService)')
content = content.replace('View(this)', 'View(this@ScreenCaptureService)')

# Wait, in triggerScreenUpdate, instance is missing because we need to add triggerScreenUpdate to companion object?
# No, we can just call it on instance
content = content.replace('fun triggerScreenUpdate', 'companion object {\n        fun triggerScreenUpdate() {\n            instance?.triggerScreenUpdateInternal()\n        }\n    }\n\n    fun triggerScreenUpdateInternal')

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)