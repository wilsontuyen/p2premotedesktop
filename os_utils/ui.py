import sys

if sys.platform == "win32":
    from os_utils.windows_ui import *
elif sys.platform.startswith("linux"):
    from os_utils.linux_ui import *
else:
    raise NotImplementedError(f"Hệ điều hành không được hỗ trợ: {sys.platform}")
