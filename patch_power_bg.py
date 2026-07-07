import os

def apply_patch():
    target = r"d:\Data\AG\remote_desktop\app.py"
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    old_c = """                        if show_power_button:
                            power_bg_base = (cad_bg_color[0], cad_bg_color[1], cad_bg_color[2]) # just take the color
                            power_bg = power_bg_base if power_is_hover else (int(power_bg_base[0]*0.8), int(power_bg_base[1]*0.8), int(power_bg_base[2]*0.8))
                            pygame.draw.rect(screen, power_bg, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)
                            
                            try:
                                symbol_font = pygame.font.SysFont("Wingdings", 16)
                                power_text_surf = symbol_font.render("¤", True, cad_text_color)
                            except:
                                power_text_surf = btn_font.render("¤", True, cad_text_color)"""
                                
    new_c = """                        if show_power_button:
                            power_bg = (240, 240, 240) if power_is_hover else (255, 255, 255)
                            pygame.draw.rect(screen, power_bg, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)
                            
                            try:
                                symbol_font = pygame.font.SysFont("Wingdings", 16)
                                power_text_surf = symbol_font.render("¤", True, (0, 0, 0))
                            except:
                                power_text_surf = btn_font.render("¤", True, (0, 0, 0))"""

    if old_c not in content:
        print(f"Failed to find a chunk in {target}!")
        return
    content = content.replace(old_c, new_c, 1)

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Patched app.py to use black text on white background for power button.")

if __name__ == "__main__":
    apply_patch()
