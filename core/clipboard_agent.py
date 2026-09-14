import sys

if sys.platform == "win32":
    from os_utils.windows_clipboard import *
elif sys.platform.startswith("linux"):
    from os_utils.linux_clipboard import *
elif sys.platform == "darwin":
    from os_utils.mac_clipboard import *
else:
    raise NotImplementedError(f"Hệ điều hành không được hỗ trợ: {sys.platform}")

if "CLIPBOARD_PKT_TYPES" not in globals():
    CLIPBOARD_PKT_TYPES = (
        "batch_start", "file_start", "file_chunk", "file_end", "batch_end",
        "files_copied_meta", "request_files", "cancel_transfer", "cancel_ack",
        "clipboard_text", "clipboard_image", "clear_clipboard",
        "resume_query", "resume_state",
    )
