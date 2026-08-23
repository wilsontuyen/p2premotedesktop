import re

def insert_after(file_path, search_str, insert_str):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if insert_str not in content:
        content = content.replace(search_str, search_str + '\n' + insert_str)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

insert_after(r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\MainActivity.kt',
             'super.onCreate(savedInstanceState)',
             '        System.setProperty("java.net.preferIPv4Stack", "true")')

insert_after(r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\ScreenCaptureService.kt',
             'super.onCreate()',
             '        System.setProperty("java.net.preferIPv4Stack", "true")')