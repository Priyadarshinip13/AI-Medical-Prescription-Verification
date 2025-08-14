import pytesseract
from PIL import Image

# Optional: explicitly set path if not in PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = Image.open("pres.jpg")
text = pytesseract.image_to_string(img)
print(text)
