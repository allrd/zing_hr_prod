import pdfplumber
import pytesseract
import platform
import shutil
from pdf2image import convert_from_path
from PIL import Image
import re
import os

# -----------------------------------------------------------
# TESSERACT PATH
#pytesseract.pytesseract.tesseract_cmd = r"C:\Users\VikasTiwari\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

#if platform.system() == "Windows":
#    pytesseract.pytesseract.tesseract_cmd = (
#        r"C:\Users\VikasTiwari\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
#    )

# -----------------------------------------------------------
# POPPLER PATH FOR SCANNED PDF → IMAGE CONVERSION
#POPLER_PATH = r"C:\poppler-25.07.0\Library\bin"
POPLER_PATH= None
# -----------------------------------------------------------


# ----------------------------
# ALL DATE KEYWORDS
# ----------------------------
date_keywords = [
    "date", "invoice date", "bill date", "issued on", "created on",
    "billing date", "payment date", "statement date", "generation date",
    "document date", "transaction date", "txn date", "dated"
]

# ----------------------------
# ALL DATE PATTERNS
# ----------------------------
date_patterns = [
    r"\b(0[1-9]|[12][0-9]|3[01])[\/\-\.](0[1-9]|1[0-2])[\/\-\.](20\d{2})\b",
    r"\b(20\d{2})[\/\-\.](0[1-9]|1[0-2])[\/\-\.](0[1-9]|[12][0-9]|3[01])\b",
    r"\b(0[1-9]|1[0-2])[\/\-\.](0[1-9]|[12][0-9]|3[01])[\/\-\.](20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01]) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d{2})\b",
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (0?[1-9]|[12][0-9]|3[01]) (20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01])-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01]) (January|February|March|April|May|June|July|August|September|October|November|December),? (20\d{2})\b",
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (0?[1-9]|[12][0-9]|3[01]),? (20\d{2})\b",
    r"\b(0[1-9]|[12][0-9]|3[01])\-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\-(20\d{2})\b"

]


# ----------------------------
# UNIVERSAL TEXT EXTRACTOR (PDF + IMAGE + OCR)
# ----------------------------
def extract_text_full(filepath):

    ext = filepath.lower().split(".")[-1]

    # -------------------- PDF --------------------
    if ext == "pdf":
        try:
            pdf = pdfplumber.open(filepath)
            full_text = ""

            for pg in pdf.pages:
                txt = pg.extract_text()

                if txt and txt.strip():
                    full_text += "\n" + txt
                else:
                    # OCR for scanned pages
                    images = convert_from_path(
                        filepath,
                        first_page=pg.page_number,
                        last_page=pg.page_number,
#                        poppler_path=POPLER_PATH
                    )
                    for img in images:
                        img = img.rotate(-90, expand=True)
                        full_text += pytesseract.image_to_string(img)

            pdf.close()
            return full_text

        except Exception:
            # FULL fallback OCR for entire PDF
            images = convert_from_path(filepath)
            text_all = ""
            for img in images:
                img = img.rotate(-90, expand=True)
                text_all += pytesseract.image_to_string(img)
            return text_all

    # -------------------- IMAGE --------------------
    else:
        img = Image.open(filepath)
        img = img.rotate(-90, expand=True)
        return pytesseract.image_to_string(img)


# ----------------------------
# EXTRACT DATE FROM TEXT
# ----------------------------
def extract_date_from_text(text):
    if not text:
        return None

    lines = text.split("\n")

    # keyword-based first
    for line in lines:
        for key in date_keywords:
            if key.lower() in line.lower():
                for dp in date_patterns:
                    found = re.search(dp, line, re.IGNORECASE)
                    if found:
                        return found.group(0)

    # global search fallback
    for dp in date_patterns:
        found = re.search(dp, text, re.IGNORECASE)
        if found:
            return found.group(0)

    return None


# ----------------------------
# MAIN TEST (WORKS FOR PDF + IMAGES)
# ----------------------------
test_files = [
    # "bills_folder/invoice-4059842024232149839.pdf"
]

for file in test_files:
    print("\n-------------------------------------")
    print("FILE:", file)

    text = extract_text_full(file)
    print("\nTEXT PREVIEW:\n", text[:500])

    date_found = extract_date_from_text(text)
    print("\n>> Extracted Date:", date_found if date_found else "Date not found")
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os

# -----------------------------------------------------------
# TESSERACT PATH
#pytesseract.pytesseract.tesseract_cmd = r"C:\Users\VikasTiwari\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# -----------------------------------------------------------
# POPPLER PATH FOR SCANNED PDF → IMAGE CONVERSION
#POPLER_PATH = r"C:\poppler-25.07.0\Library\bin"
POPLER_PATH = None
# -----------------------------------------------------------


# ----------------------------
# ALL DATE KEYWORDS
# ----------------------------
date_keywords = [
    "date", "invoice date", "bill date", "issued on", "created on",
    "billing date", "payment date", "statement date", "generation date",
    "document date", "transaction date", "txn date", "dated"
]

# ----------------------------
# ALL DATE PATTERNS
# ----------------------------
date_patterns = [
    r"\b(0[1-9]|[12][0-9]|3[01])[\/\-\.](0[1-9]|1[0-2])[\/\-\.](20\d{2})\b",
    r"\b(20\d{2})[\/\-\.](0[1-9]|1[0-2])[\/\-\.](0[1-9]|[12][0-9]|3[01])\b",
    r"\b(0[1-9]|1[0-2])[\/\-\.](0[1-9]|[12][0-9]|3[01])[\/\-\.](20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01]) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d{2})\b",
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (0?[1-9]|[12][0-9]|3[01]) (20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01])-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(20\d{2})\b",
    r"\b(0?[1-9]|[12][0-9]|3[01]) (January|February|March|April|May|June|July|August|September|October|November|December),? (20\d{2})\b",
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (0?[1-9]|[12][0-9]|3[01]),? (20\d{2})\b",
    r"\b(0[1-9]|[12][0-9]|3[01])\-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\-(20\d{2})\b"

]


# ----------------------------
# UNIVERSAL TEXT EXTRACTOR (PDF + IMAGE + OCR)
# ----------------------------
def extract_text_full(filepath):

    ext = filepath.lower().split(".")[-1]

    # -------------------- PDF --------------------
    if ext == "pdf":
        try:
            pdf = pdfplumber.open(filepath)
            full_text = ""

            for pg in pdf.pages:
                txt = pg.extract_text()

                if txt and txt.strip():
                    full_text += "\n" + txt
                else:
                    # OCR for scanned pages
                    images = convert_from_path(
                        filepath,
                        first_page=pg.page_number,
                        last_page=pg.page_number,
                        poppler_path=POPLER_PATH
                    )
                    for img in images:
                        img = img.rotate(-90, expand=True)
                        full_text += pytesseract.image_to_string(img)

            pdf.close()
            return full_text

        except Exception:
            # FULL fallback OCR for entire PDF
            images = convert_from_path(filepath, poppler_path=POPLER_PATH)
            text_all = ""
            for img in images:
                img = img.rotate(-90, expand=True)
                text_all += pytesseract.image_to_string(img)
            return text_all

    # -------------------- IMAGE --------------------
    else:
        img = Image.open(filepath)
        img = img.rotate(-90, expand=True)
        return pytesseract.image_to_string(img)


# ----------------------------
# EXTRACT DATE FROM TEXT
# ----------------------------
def extract_date_from_text(text):
    if not text:
        return None

    lines = text.split("\n")

    # keyword-based first
    for line in lines:
        for key in date_keywords:
            if key.lower() in line.lower():
                for dp in date_patterns:
                    found = re.search(dp, line, re.IGNORECASE)
                    if found:
                        return found.group(0)

    # global search fallback
    for dp in date_patterns:
        found = re.search(dp, text, re.IGNORECASE)
        if found:
            return found.group(0)

    return None


# ----------------------------
# MAIN TEST (WORKS FOR PDF + IMAGES)
# ----------------------------
test_files = [
    # "bills_folder/invoice-4059842024232149839.pdf"
]

for file in test_files:
    print("\n-------------------------------------")
    print("FILE:", file)

    text = extract_text_full(file)
    print("\nTEXT PREVIEW:\n", text[:500])

    date_found = extract_date_from_text(text)
    print("\n>> Extracted Date:", date_found if date_found else "Date not found")
