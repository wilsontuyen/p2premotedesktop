import os

def apply_patch():
    target = r"d:\Data\AG\remote_desktop\app.py"
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    old = """                            power_bg = cad_bg_color if power_is_hover else (cad_bg_color[0]*0.9, cad_bg_color[1]*0.9, cad_bg_color[2]*0.9)"""
    new = """                            power_bg_base = (cad_bg_color[0], cad_bg_color[1], cad_bg_color[2]) # just take the color
                            power_bg = power_bg_base if power_is_hover else (int(power_bg_base[0]*0.8), int(power_bg_base[1]*0.8), int(power_bg_base[2]*0.8))"""
    
    if old in content:
        content = content.replace(old, new)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fixed power_bg.")
    else:
        print("Could not find power_bg line.")

if __name__ == "__main__":
    apply_patch()
