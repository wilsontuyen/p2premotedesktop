import os
import glob

temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
print(f"Temp Dir: {temp_dir}")
if os.path.exists(temp_dir):
    files = glob.glob(os.path.join(temp_dir, "*"))
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        print(f"File: {os.path.basename(f)} | Size: {os.path.getsize(f)} | Modified: {os.path.getmtime(f)}")
else:
    print("Temp directory does not exist.")
