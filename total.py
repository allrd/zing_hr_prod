import pdfplumber
import re
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import platform
import shutil

# -----------------------------------------------------------
# OS-AWARE CONFIGURATION
# -----------------------------------------------------------

# Tesseract
#if platform.system() == "Windows":
#    pytesseract.pytesseract.tesseract_cmd = (
#        r"C:\Users\VikasTiwari\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
#    )
#else:
#    if not shutil.which("tesseract"):
#        raise RuntimeError("Tesseract is not installed or not in PATH")

# Poppler
if platform.system() == "Windows":
    POPPLER_PATH = r"C:\poppler-25.07.0\Library\bin"
else:
    POPPLER_PATH = None


# -------------------------------------------------------------------------------------
# YOUR ORIGINAL FUNCTION (UNCHANGED)
# -------------------------------------------------------------------------------------
def extract_total(text):
    text_clean = text.replace(",", "")

    address_words = [
        "india", "karnataka", "maharashtra", "thane", "bengaluru", "mumbai",
        "road", "village", "taluka", "district", "dist", "pin", "pincode",
        "state", "west", "east", "south", "north"
    ]

    patterns = [
        r"\bGrand\s*Total\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\bTotal\s*Due\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\bDue\s*(Amount)?\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\bTotal\s*(Amount|Payable|Bill)\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\b(Invoice|Net)\s*(Total|Amount)\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\b(Payment|Paid|VISA|Card|Cash|UPI)\s*[A-Za-z]*\s*[₹RsINR\.\s]*([0-9]+\.[0-9]+|[0-9]+)",
        r"\bTotal[\s:A-Za-z]*[₹RsINR]*\.?([0-9]+\.[0-9]+|[0-9]+)"
    ]

    def is_not_address(line):
        return not any(w in line.lower() for w in address_words)

    for pat in patterns:
        m = re.search(pat, text_clean, re.IGNORECASE)
        if m:
            amt = m.group(m.lastindex)
            if amt and float(amt) > 50:
                return amt

    for line in text_clean.split("\n"):
        if not line.strip():
            continue
        if not is_not_address(line):
            continue
        if any(k in line.lower() for k in ["total", "due", "payable", "amount"]):
            nums = re.findall(r"[0-9]+\.[0-9]+|[0-9]+", line)
            nums = [n for n in nums if 50 < float(n) < 50000]
            if nums:
                return max(nums, key=lambda x: float(x))

    return "Total not found"


# -------------------------------------------------------------------------------------
# OCR HELPERS
# -------------------------------------------------------------------------------------
def _ocr_best(img):
    best = ""
    for angle in (0, 90, 180, 270):
        text = pytesseract.image_to_string(img.rotate(angle, expand=True))
        if len(text) > len(best):
            best = text
    return best


# -------------------------------------------------------------------------------------
# UNIVERSAL TEXT EXTRACTOR (VM SAFE)
# -------------------------------------------------------------------------------------
def extract_text_full(path):

    if path.lower().endswith(".pdf"):
        text_out = ""

        # 1️⃣ pdfplumber first
        try:
            with pdfplumber.open(path) as pdf:
                for pg in pdf.pages:
                    txt = pg.extract_text()
                    if txt and txt.strip():
                        text_out += "\n" + txt

            if text_out.strip():
                return text_out
        except Exception as e:
            print("pdfplumber failed:", e)

        # 2️⃣ OCR fallback
        try:
            kwargs = {"dpi": 300}
            if POPPLER_PATH:
                kwargs["poppler_path"] = POPPLER_PATH

            imgs = convert_from_path(path, **kwargs)
            for img in imgs:
                text_out += "\n" + _ocr_best(img)
            return text_out
        except Exception as e:
            print("pdf2image failed:", e)
            return ""

    else:
        img = Image.open(path)
        return _ocr_best(img)


# -------------------------------------------------------------------------------------
# TEST DRIVER
# -------------------------------------------------------------------------------------
files = [
    # "bills_folder/example.pdf"
]

for file in files:
    print("\n===== FILE:", file, "=====\n")
    text = extract_text_full(file)
    print(text[:500])
    total = extract_total(text)
    print("\n>> Extracted Total:", total)

