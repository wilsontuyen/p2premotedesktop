import cv2
import numpy as np

def smooth_edges(input_path, output_path):
    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    b, g, r, a = cv2.split(img)
    
    # Smooth the alpha channel
    a_blurred = cv2.GaussianBlur(a, (3, 3), 0)
    
    # Only keep the blurred alpha where original alpha was near edge, to prevent dilating the object
    # Or just use the blurred alpha
    
    rgba = cv2.merge([b, g, r, a_blurred])
    cv2.imwrite(output_path, rgba)

if __name__ == "__main__":
    smooth_edges('app_icon_no_bg.png', 'app_icon.png')
