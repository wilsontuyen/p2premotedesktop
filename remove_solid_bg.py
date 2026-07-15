import cv2
import numpy as np

def remove_solid_bg(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None:
        print("Could not read image")
        return

    h, w = img.shape[:2]
    # Create mask for floodFill (must be h+2, w+2)
    mask = np.zeros((h+2, w+2), np.uint8)

    # The background is a gradient of gray around 160-170.
    # We will floodFill from multiple points along the top and sides.
    loDiff = (12, 12, 12)
    upDiff = (12, 12, 12)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY

    # Flood fill from corners and middle of edges
    pts = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1), (w//2, 0), (0, h//2), (w-1, h//2)]
    for pt in pts:
        cv2.floodFill(img, mask, pt, (0, 0, 0), loDiff, upDiff, flags)

    # Trim mask
    mask = mask[1:h+1, 1:w+1]

    # Blur the mask slightly to anti-alias the edges
    mask_blurred = cv2.GaussianBlur(mask, (3, 3), 0)

    # Add alpha channel
    b, g, r = cv2.split(img)
    alpha = 255 - mask_blurred

    rgba = cv2.merge([b, g, r, alpha])

    cv2.imwrite(output_path, rgba)
    print("Done")

if __name__ == "__main__":
    input_path = r"C:\Users\Tuyen\.gemini\antigravity\brain\d628f4ec-18ae-495d-8c08-aef6fcd09ccc\media__1784072231780.jpg"
    remove_solid_bg(input_path, 'app_icon.png')
