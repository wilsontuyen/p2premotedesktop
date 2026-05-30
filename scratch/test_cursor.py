from PIL import Image, ImageDraw
img = Image.new("RGB", (50, 50), "blue")
draw = ImageDraw.Draw(img)
cx, cy = 10, 10
arrow_coords = [
    (cx, cy), (cx, cy+17), (cx+4, cy+13), 
    (cx+7, cy+20), (cx+9, cy+19), (cx+6, cy+12), 
    (cx+11, cy+12)
]
draw.polygon(arrow_coords, fill=(255, 255, 255), outline=(0, 0, 0))
img.save("c:\\Users\\Tuyen\\.gemini\\antigravity\\scratch\\remote_desktop\\scratch\\test_cursor.png")
