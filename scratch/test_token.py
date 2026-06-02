import win32ts
import win32security
import win32api
import win32con

active_session_id = win32ts.WTSGetActiveConsoleSessionId()
print("Session ID:", active_session_id)
try:
    h_token = win32ts.WTSQueryUserToken(active_session_id)
    print("User token:", h_token)
    try:
        elevation_type = win32security.GetTokenInformation(h_token, win32security.TokenElevationType)
        print("Elevation type:", elevation_type)
        if elevation_type == 3: # TokenElevationTypeLimited
            linked = win32security.GetTokenInformation(h_token, win32security.TokenLinkedToken)
            print("Linked token:", linked)
    except Exception as e:
        print("Error getting token info:", e)
except Exception as e:
    print("Error querying user token:", e)
