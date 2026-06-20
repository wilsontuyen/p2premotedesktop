import os
import glob

app_dir = r"C:\Apps\P2P"
print(f"App Dir: {app_dir}")
if os.path.exists(app_dir):
    files = glob.glob(os.path.join(app_dir, "*"))
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        print(f"File: {os.path.basename(f)} | Size: {os.path.getsize(f)} | Modified: {os.path.getmtime(f)}")
else:
    print("Deployment directory does not exist.")
