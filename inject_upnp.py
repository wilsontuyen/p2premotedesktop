import re

dt_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(dt_file, 'r', encoding='utf-8') as f:
    dt_content = f.read()

# Find startServerAndWait and inject UPnPManager.openPortBackground(port)
# Let's insert it right after isRunning = true
start_pattern = re.compile(r'(fun startServerAndWait.*?isRunning = true)', re.DOTALL)
dt_content = start_pattern.sub(r'\1\n        UPnPManager.openPortBackground(port)', dt_content)

# Find stopDataTransfer and inject UPnPManager.closeActivePort()
stop_pattern = re.compile(r'(fun stopDataTransfer\(\) \{.*?isRunning = false)', re.DOTALL)
dt_content = stop_pattern.sub(r'\1\n        UPnPManager.closeActivePort()', dt_content)

with open(dt_file, 'w', encoding='utf-8') as f:
    f.write(dt_content)