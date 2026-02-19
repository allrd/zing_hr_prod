import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os
import platform
import shutil

# -----------------------------------------------------------
# OS-AWARE CONFIGURATION
# -----------------------------------------------------------

# Tesseract config
TESSERACT_CONFIG = "--psm 3"

#if platform.system() == "Windows":
#    pytesseract.pytesseract.tesseract_cmd = (
#        r"C:\Users\VikasTiwari\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
#    )
#else:
#    # Linux / VM safety check
#    if not shutil.which("tesseract"):
#        raise RuntimeError("Tesseract is not installed or not in PATH")

# Poppler config
if platform.system() == "Windows":
    POPPLER_PATH = r"C:\poppler-25.07.0\Library\bin"
else:
    POPPLER_PATH = None


# ------------------------- INVOICE EXTRACTION LOGIC (UNCHANGED) -------------------------
def extract_invoice(text):

    text_clean = (
        text.replace(",", " ")
            .replace(":", " ")
            .replace("#", " # ")
            .replace("-", " ")
    ).lower()

    address_words = [
        "india","karnataka","maharashtra","thane","bengaluru","mumbai",
        "road","village","taluka","district","dist","pin","pincode",
        "state","west","east","south","north"
    ]

    def is_not_address(line):
        return not any(w in line.lower() for w in address_words)

    invoice_keywords = [
        "invoice number", "invoice no", "invoice id", "invoice #",
        "tax invoice", "bill number", "bill no", "inv no", "invoice", "patient id"
    ]

    invoice_patterns = [
        r"(?:invoice\s*number|invoice\s*no|invoice\s*#|invoice\s*id|bill\s*no|bill\s*number|patient\s*id|inv\s*no)[\s:#]*([A-Za-z0-9\-\/]+)",
        r"\b([A-Z]{2,4}\d{6,12})\b",
    ]

    lines = text.split("\n")

    for line in lines:
        if not is_not_address(line):
            continue
        if any(k in line.lower() for k in invoice_keywords):
            for pat in invoice_patterns:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    return m.group(1).strip()

    for pat in invoice_patterns:
        m = re.search(pat, text_clean, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    order_match = re.search(r"\bOD[0-9]{10,}\b", text_clean)
    if order_match:
        return "Invoice Missing - Using OrderID: " + order_match.group(0)

    return "Invoice Not Found"


# -------------------------- STRICT MATCHING LOGIC --------------------------
def normalize_invoice(value):
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value).lower()


def check_known_invoice_in_text(text, known_invoice):
    if not known_invoice:
        return False

    norm_known = normalize_invoice(known_invoice)
    candidates = re.findall(r"[A-Za-z0-9\-\/]+", text)

    for c in candidates:
        if normalize_invoice(c) == norm_known:
            return True

    return False


# ------------------------ UNIVERSAL PDF / IMAGE TEXT EXTRACTOR -------------------------
def extract_text_full(filepath):

    ext = filepath.lower().split(".")[-1]

    # ---------------------------- PDF ----------------------------
    if ext == "pdf":
        text_out = ""

        # 1️⃣ Try pdfplumber
        try:
            with pdfplumber.open(filepath) as pdf:
                for pg in pdf.pages:
                    txt = pg.extract_text()
                    if txt and txt.strip():
                        text_out += "\n" + txt

            if text_out.strip():
                return text_out
        except Exception as e:
            print("pdfplumber failed:", e)

        # 2️⃣ OCR fallback with pdf2image
        try:
            kwargs = {"dpi": 300}
            if POPPLER_PATH:
                kwargs["poppler_path"] = POPPLER_PATH

            images = convert_from_path(filepath, **kwargs)

            for img in images:
                text_out += pytesseract.image_to_string(img, config=TESSERACT_CONFIG)

            return text_out
        except Exception as e:
            print("pdf2image failed:", e)
            return ""

    # ---------------------------- IMAGE ----------------------------
    else:
        img = Image.open(filepath)
        return pytesseract.image_to_string(img, config=TESSERACT_CONFIG)


# -------------------------- MAIN EXECUTION ---------------------------
image_paths = [
    # "bills_folder/sample.pdf"
]

known_invoice_number = "M06HL24I11684390"

for file in image_paths:
    print("\n--------------------------------------------")
    print("FILE:", file)

    text = extract_text_full(file)
    print("\nEXTRACTED TEXT (PREVIEW):")
    print(text[:500])

    invoice_no = extract_invoice(text)
    print("\n>> Extracted Invoice No:", invoice_no)

    contains = check_known_invoice_in_text(text, known_invoice_number)
    print(f">> Known Invoice ({known_invoice_number}) Present?: {contains}")

