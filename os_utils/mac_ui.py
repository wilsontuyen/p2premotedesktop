from utils.logger import log_debug

def get_file_icon_as_image(file_name, size="large"):
    # On Linux, extracting icons dynamically is more complex and depends on the DE (GNOME/KDE/etc)
    # For MVP, we simply return None and let the UI use a default icon.
    return None
