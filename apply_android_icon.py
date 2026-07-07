import os
import shutil
from PIL import Image

src_icon = r"d:\Data\AG\remote_desktop\app_icon.png"
android_res_dir = r"d:\SOFT\Coder\Android\app\src\main\res"

sizes = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192
}

try:
    img = Image.open(src_icon)
    
    for density, size in sizes.items():
        folder = os.path.join(android_res_dir, f"mipmap-{density}")
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        # Resize image
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        
        # Save as ic_launcher.png and ic_launcher_round.png
        resized.save(os.path.join(folder, "ic_launcher.png"))
        resized.save(os.path.join(folder, "ic_launcher_round.png"))
        
        # Delete old .webp if they exist
        webp_normal = os.path.join(folder, "ic_launcher.webp")
        webp_round = os.path.join(folder, "ic_launcher_round.webp")
        if os.path.exists(webp_normal):
            os.remove(webp_normal)
        if os.path.exists(webp_round):
            os.remove(webp_round)
            
    # Remove anydpi-v26 to ensure the PNGs are used
    anydpi_folder = os.path.join(android_res_dir, "mipmap-anydpi-v26")
    if os.path.exists(anydpi_folder):
        shutil.rmtree(anydpi_folder)
        
    # Remove vector drawables just in case
    bg_xml = os.path.join(android_res_dir, "drawable", "ic_launcher_background.xml")
    fg_xml = os.path.join(android_res_dir, "drawable", "ic_launcher_foreground.xml")
    if os.path.exists(bg_xml):
        os.remove(bg_xml)
    if os.path.exists(fg_xml):
        os.remove(fg_xml)

    print("Successfully applied the new icon to the Android project!")
except Exception as e:
    print(f"Error: {e}")
