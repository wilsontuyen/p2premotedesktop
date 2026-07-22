import sys

if sys.platform == "win32":
    from os_utils.windows_input import *
    from os_utils.windows_input import _remote_modifier_keys
elif sys.platform.startswith("linux"):
    from os_utils.linux_input import *
    from os_utils.linux_input import _remote_modifier_keys
elif sys.platform == "darwin":
    from os_utils.mac_input import *
    from os_utils.mac_input import _remote_modifier_keys
else:
    raise NotImplementedError(f"Hệ điều hành không được hỗ trợ: {sys.platform}")
