import time
from PIL import Image, ImageChops

def test():
    img1 = Image.new('RGB', (1920, 1080), color = 'red')
    img2 = Image.new('RGB', (1920, 1080), color = 'red')
    
    t0 = time.time()
    for _ in range(30):
        bbox = ImageChops.difference(img1, img2).getbbox()
    t1 = time.time()
    print(f"Same image bbox: {bbox}")
    print(f"Full size getbbox took: {(t1 - t0) / 30:.5f}s per frame")
    
    img2.putpixel((500, 500), (255, 0, 1)) # 1 channel changed by 1

    t0 = time.time()
    for _ in range(30):
        bbox = ImageChops.difference(img1, img2).getbbox()
    t1 = time.time()
    print(f"Diff image bbox: {bbox}")
    print(f"Full size getbbox took: {(t1 - t0) / 30:.5f}s per frame")

test()
