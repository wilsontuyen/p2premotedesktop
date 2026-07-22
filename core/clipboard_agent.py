import sys

if sys.platform == "win32":
    from os_utils.windows_clipboard import *
elif sys.platform.startswith("linux"):
    from os_utils.linux_clipboard import *
elif sys.platform == "darwin":
    from os_utils.mac_clipboard import *
else:
    raise NotImplementedError(f"Hệ điều hành không được hỗ trợ: {sys.platform}")
