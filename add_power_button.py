import os

def apply_patch():
    target = r"d:\Data\AG\remote_desktop\app.py"
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    # Chunk 1
    old_c1 = """                min_btn_w, min_btn_h = 40, 22
                cad_btn_w, cad_btn_h = 145, 22
                file_btn_w, file_btn_h = 110, 22
                rec_btn_w, rec_btn_h = 30, 22
                close_btn_w, close_btn_h = 40, 22
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                
                show_cad_button = show_buttons and not is_android
                show_file_button = show_buttons and is_android"""
    
    new_c1 = """                min_btn_w, min_btn_h = 40, 22
                cad_btn_w, cad_btn_h = 145, 22
                file_btn_w, file_btn_h = 110, 22
                power_btn_w, power_btn_h = 75, 22
                rec_btn_w, rec_btn_h = 30, 22
                close_btn_w, close_btn_h = 40, 22
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                
                show_cad_button = show_buttons and not is_android
                show_file_button = show_buttons and is_android
                show_power_button = show_buttons and is_android"""
    
    # Chunk 2
    old_c2 = """                total_w = 0
                if show_buttons:
                    total_w = min_btn_w + 10 + (file_btn_w + 10 if show_file_button else 0) + (cad_btn_w + 10 if show_cad_button else 0) + rec_btn_w + 10 + close_btn_w
                    
                start_x = (window_w - total_w) // 2
                
                if show_buttons:
                    min_btn_rect = pygame.Rect(start_x, 0, min_btn_w, min_btn_h)
                    current_x = start_x + min_btn_w + 10
                    
                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_cad_button:
                        cad_btn_rect = pygame.Rect(current_x, 0, cad_btn_w, cad_btn_h)
                        current_x += cad_btn_w + 10
                    else:
                        cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    rec_btn_rect = pygame.Rect(current_x, 0, rec_btn_w, rec_btn_h)
                    current_x += rec_btn_w + 10
                    close_btn_rect = pygame.Rect(current_x, 0, close_btn_w, close_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    file_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    rec_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_buttons else False
                file_is_hover = file_btn_rect.collidepoint(mx, my) if show_buttons else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_buttons else False
                rec_is_hover = rec_btn_rect.collidepoint(mx, my) if show_buttons else False
                close_is_hover = close_btn_rect.collidepoint(mx, my) if show_buttons else False"""

    new_c2 = """                total_w = 0
                if show_buttons:
                    total_w = min_btn_w + 10 + (file_btn_w + 10 if show_file_button else 0) + (power_btn_w + 10 if show_power_button else 0) + (cad_btn_w + 10 if show_cad_button else 0) + rec_btn_w + 10 + close_btn_w
                    
                start_x = (window_w - total_w) // 2
                
                if show_buttons:
                    min_btn_rect = pygame.Rect(start_x, 0, min_btn_w, min_btn_h)
                    current_x = start_x + min_btn_w + 10
                    
                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_cad_button:
                        cad_btn_rect = pygame.Rect(current_x, 0, cad_btn_w, cad_btn_h)
                        current_x += cad_btn_w + 10
                    else:
                        cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    rec_btn_rect = pygame.Rect(current_x, 0, rec_btn_w, rec_btn_h)
                    current_x += rec_btn_w + 10
                    close_btn_rect = pygame.Rect(current_x, 0, close_btn_w, close_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    file_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    power_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    rec_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_buttons else False
                file_is_hover = file_btn_rect.collidepoint(mx, my) if show_buttons else False
                power_is_hover = power_btn_rect.collidepoint(mx, my) if show_buttons else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_buttons else False
                rec_is_hover = rec_btn_rect.collidepoint(mx, my) if show_buttons else False
                close_is_hover = close_btn_rect.collidepoint(mx, my) if show_buttons else False"""

    # Chunk 3
    old_c3 = """                    elif event.type == pygame.MOUSEMOTION:
                        if show_buttons and (min_btn_rect.collidepoint(event.pos) or file_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or rec_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)):
                            continue"""
    new_c3 = """                    elif event.type == pygame.MOUSEMOTION:
                        if show_buttons and (min_btn_rect.collidepoint(event.pos) or file_btn_rect.collidepoint(event.pos) or power_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or rec_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)):
                            continue"""

    # Chunk 4
    old_c4 = """                        if show_buttons and cad_btn_rect.collidepoint(event.pos):"""
    new_c4 = """                        if show_buttons and power_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Power Button Clicked. Sending power key event to Android.")
                                send_event({"type": "key_event", "key": "power", "pressed": True})
                            continue
                        if show_buttons and cad_btn_rect.collidepoint(event.pos):"""

    # Chunk 5
    old_c5 = """                        if show_file_button:
                            pygame.draw.rect(screen, file_bg_color, file_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, file_btn_rect, width=1, border_radius=4)
                            
                            file_text_surf = btn_font.render("Chuyển tệp", True, file_text_color)
                            file_text_rect = file_text_surf.get_rect(center=file_btn_rect.center)
                            screen.blit(file_text_surf, file_text_rect)

                        if show_cad_button:"""
    new_c5 = """                        if show_file_button:
                            pygame.draw.rect(screen, file_bg_color, file_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, file_btn_rect, width=1, border_radius=4)
                            
                            file_text_surf = btn_font.render("Chuyển tệp", True, file_text_color)
                            file_text_rect = file_text_surf.get_rect(center=file_btn_rect.center)
                            screen.blit(file_text_surf, file_text_rect)

                        if show_power_button:
                            power_bg = cad_bg_color if power_is_hover else (cad_bg_color[0]*0.9, cad_bg_color[1]*0.9, cad_bg_color[2]*0.9)
                            pygame.draw.rect(screen, power_bg, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)
                            
                            power_text_surf = btn_font.render("Nguồn", True, cad_text_color)
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            screen.blit(power_text_surf, power_text_rect)

                        if show_cad_button:"""

    changes = [(old_c1, new_c1), (old_c2, new_c2), (old_c3, new_c3), (old_c4, new_c4), (old_c5, new_c5)]
    
    for old_txt, new_txt in changes:
        if old_txt not in content:
            print(f"Failed to find a chunk in {target}!")
            return
        content = content.replace(old_txt, new_txt, 1)

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Patched app.py successfully.")

if __name__ == "__main__":
    apply_patch()
