import cv2
import numpy as np

def remove_checkerboard(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None:
        print("Could not read image")
        return

    h, w = img.shape[:2]
    # Create a mask for floodFill. It needs to be 2 pixels wider and taller than the image
    mask = np.zeros((h+2, w+2), np.uint8)

    # We will floodFill from multiple points along the edges to ensure we capture all background
    # The checkerboard has two colors, so we floodFill with a small tolerance
    loDiff = (10, 10, 10)
    upDiff = (10, 10, 10)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY

    # Flood fill from the 4 corners
    corners = [(0, 0), (0, h-1), (w-1, 0), (w-1, h-1)]
    for pt in corners:
        cv2.floodFill(img, mask, pt, (0, 0, 0), loDiff, upDiff, flags)

    # The mask now contains 255 for the background
    # We want to make the background transparent
    # The mask has size (h+2, w+2), we need to trim it
    mask = mask[1:h+1, 1:w+1]

    # Add alpha channel
    b, g, r = cv2.split(img)
    alpha = np.where(mask == 255, 0, 255).astype('uint8')

    rgba = cv2.merge([b, g, r, alpha])

    cv2.imwrite(output_path, rgba)
    print("Done")

if __name__ == "__main__":
    remove_checkerboard('app_icon.png', 'app_icon_no_bg2.png')
