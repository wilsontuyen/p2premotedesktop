import cv2
import numpy as np

def remove_background(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None:
        print("Could not read image")
        return

    # Create a mask
    mask = np.zeros(img.shape[:2], np.uint8)

    # Temporary arrays used by grabCut
    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)

    # Define a bounding box around the main object.
    # We will assume the object is mostly in the center.
    # Let's say we leave a 10% margin on all sides.
    h, w = img.shape[:2]
    margin_x = int(w * 0.05)
    margin_y = int(h * 0.05)
    rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

    print("Running grabCut...")
    cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)

    # Modify the mask to create a binary mask (0 for bg, 1 for fg)
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

    # Add an alpha channel to the original image
    b, g, r = cv2.split(img)
    alpha = mask2 * 255

    # Refine the edges slightly to remove some checkerboard remnants
    # but grabCut usually leaves some hard edges.
    
    rgba = cv2.merge([b, g, r, alpha])

    print("Saving result...")
    cv2.imwrite(output_path, rgba)
    print("Done")

if __name__ == "__main__":
    remove_background('app_icon.png', 'app_icon_no_bg.png')
