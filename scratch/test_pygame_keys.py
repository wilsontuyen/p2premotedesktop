import pygame

def get_char(key, unicode_char):
    key_name = pygame.key.name(key)
    char_to_send = key_name
    if unicode_char and len(unicode_char) == 1 and ord(unicode_char) >= 32:
        char_to_send = unicode_char
    return char_to_send

print("Delete:", repr(get_char(pygame.K_DELETE, '\x7f')))
# Home doesn't have unicode usually, but what if it's returning empty string
print("Home:", repr(get_char(pygame.K_HOME, '')))
