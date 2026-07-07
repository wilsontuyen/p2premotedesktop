import os

def apply_patch():
    target = r"d:\Data\AG\remote_desktop\app.py"
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    old_c3 = """                            try:
                                symbol_font = pygame.font.SysFont("Segoe UI Symbol", 16)
                                power_text_surf = symbol_font.render("⏼", True, cad_text_color)
                            except:
                                power_text_surf = btn_font.render("⏼", True, cad_text_color)
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            # Shift a bit up for symbol centering
                            power_text_rect.y -= 1
                            screen.blit(power_text_surf, power_text_rect)"""
                            
    new_c3 = """                            try:
                                symbol_font = pygame.font.SysFont("Wingdings", 16)
                                power_text_surf = symbol_font.render("¤", True, cad_text_color)
                            except:
                                power_text_surf = btn_font.render("¤", True, cad_text_color)
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            # Shift a bit up for symbol centering
                            power_text_rect.y -= 1
                            screen.blit(power_text_surf, power_text_rect)"""

    if old_c3 not in content:
        print(f"Failed to find a chunk in {target}!")
        return
    content = content.replace(old_c3, new_c3, 1)

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Patched app.py to use Wingdings ¤ successfully.")

if __name__ == "__main__":
    apply_patch()
