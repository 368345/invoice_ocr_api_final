# ocr_utils.py
import re
import cv2


def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised = cv2.fastNlMeansDenoising(binary, None, 30, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    return enhanced


def safe_parse_float(value) -> float | None:
    if not value or not isinstance(value, str):
        return None
    # Extract first valid float-looking number from string
    match = re.search(r"[-+]?\d*\.\d+|\d+", value.replace(",", "."))
    return float(match.group()) if match else None
