import sys

if sys.platform == "win32":
    from os_utils.windows_system import *
elif sys.platform.startswith("linux"):
    from os_utils.linux_system import *

else:
    raise NotImplementedError(f"Hệ điều hành không được hỗ trợ: {sys.platform}")
