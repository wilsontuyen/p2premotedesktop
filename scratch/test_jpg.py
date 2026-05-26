from PIL import Image
import io

img = Image.new("RGB", (100, 100), (255, 0, 0))
buf = io.BytesIO()
img.save(buf, format="JPEG", quality=85, optimize=True, subsampling=0)
print("Saved JPEG with subsampling=0, size:", len(buf.getvalue()))
