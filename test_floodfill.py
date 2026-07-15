import cv2
import numpy as np

def test_floodfill(input_path, output_path):
    img = cv2.imread(input_path)
    h, w = img.shape[:2]
    mask = np.zeros((h+2, w+2), np.uint8)

    loDiff = (25, 25, 25)
    upDiff = (25, 25, 25)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY

    # Flood fill from the corners
    pts = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1), (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2)]
    for pt in pts:
        cv2.floodFill(img, mask, pt, (0, 0, 0), loDiff, upDiff, flags)

    mask = mask[1:h+1, 1:w+1]

    # Let's count how many pixels were filled
    print("Filled pixels:", np.sum(mask == 255))
    print("Total pixels:", h * w)

    # Blur the mask slightly
    mask_blurred = cv2.GaussianBlur(mask, (5, 5), 0)

    # Save alpha
    b, g, r = cv2.split(img)
    alpha = 255 - mask_blurred
    rgba = cv2.merge([b, g, r, alpha])
    cv2.imwrite(output_path, rgba)

if __name__ == "__main__":
    test_floodfill(r"C:\Users\Tuyen\.gemini\antigravity\brain\d628f4ec-18ae-495d-8c08-aef6fcd09ccc\media__1784072457067.jpg", "app_icon_test.png")
