import cv2
import numpy as np

def remove_perfect_bg(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None:
        print("Could not read image")
        return

    # Use float32 or int32 to avoid overflow when subtracting
    b, g, r = cv2.split(img.astype(np.int32))
    max_c = np.maximum(np.maximum(b, g), r)
    min_c = np.minimum(np.minimum(b, g), r)
    diff = max_c - min_c

    # Create mask where pixels are gray-ish and light
    # Background is a gradient from 150 to 180, mostly gray (diff < 15)
    # We use a soft transition for alpha to get smooth edges
    
    # Calculate a "background score"
    # The more it fits the background criteria, the more transparent it becomes.
    # But a hard threshold with a small blur is easier and often looks good enough for icons.
    
    mask = ((diff < 18) & (r > 120) & (r < 230)).astype(np.uint8) * 255
    
    # We want to fill any tiny holes in the foreground object that might have been accidentally masked
    # But since the background is large, let's keep it simple.
    
    # Apply a slight Gaussian blur to smooth the edges of the mask
    mask_blurred = cv2.GaussianBlur(mask, (3, 3), 0)

    # Convert original image back to uint8
    b, g, r = cv2.split(img)
    alpha = 255 - mask_blurred

    rgba = cv2.merge([b, g, r, alpha])
    cv2.imwrite(output_path, rgba)
    print("Done")

if __name__ == "__main__":
    input_path = r"C:\Users\Tuyen\.gemini\antigravity\brain\d628f4ec-18ae-495d-8c08-aef6fcd09ccc\media__1784072457067.jpg"
    remove_perfect_bg(input_path, 'app_icon.png')
