import win32event, win32con
try:
    sas_event = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_SAS_Event")
    print(f"Successfully opened: {sas_event}")
    win32event.SetEvent(sas_event)
    print("Set successfully.")
except Exception as e:
    print(f"Failed to open: {e}")
