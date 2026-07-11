import os

def apply_patch():
    target = r"d:\Data\AG\remote_desktop\app.py"
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    # Change width
    old_c1 = """                power_btn_w, power_btn_h = 75, 22"""
    new_c1 = """                power_btn_w, power_btn_h = 40, 22"""

    # Change order
    old_c2 = """                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)"""
    new_c2 = """                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)"""

    # Change render symbol
    old_c3 = """                            power_text_surf = btn_font.render(_("Nguồn"), True, cad_text_color)
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            screen.blit(power_text_surf, power_text_rect)"""
    new_c3 = """                            try:
                                symbol_font = pygame.font.SysFont("Segoe UI Symbol", 16)
                                power_text_surf = symbol_font.render("⏼", True, cad_text_color)
                            except:
                                power_text_surf = btn_font.render("⏼", True, cad_text_color)
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            # Shift a bit up for symbol centering
                            power_text_rect.y -= 1
                            screen.blit(power_text_surf, power_text_rect)"""

    changes = [(old_c1, new_c1), (old_c2, new_c2), (old_c3, new_c3)]
    
    for old_txt, new_txt in changes:
        if old_txt not in content:
            print(f"Failed to find a chunk in {target}!")
            print(f"Chunk starting with: {old_txt[:50]}")
            return
        content = content.replace(old_txt, new_txt, 1)

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Patched app.py to swap button position and use power symbol successfully.")

if __name__ == "__main__":
    apply_patch()
