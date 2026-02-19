import re
import fitz  # PyMuPDF
import easyocr
from PIL import Image, ImageOps, ImageFilter
import io
from difflib import get_close_matches
 
# -------------------------------
# Known Vendors
# -------------------------------
ride_vendors = ["OLA", "UBER", "RAPIDO"]
hotel_vendors = ["THE OBEROI","TAJ","HYATT","MARRIOTT","ITC","LEELA","NOVOTEL","WESTIN","TRIDENT","RADISSON"]
hospital_vendors = ["KOKILABEN DHIRUBHAI AMBANI HOSPITAL","NANAVATI","FORTIS","APOLLO","JASLOK","LILAVATI"]
 
# OCR correction dictionary (expanded for hospitals)
corrections = {
    "OHE OBEROI": "THE OBEROI",
    "KETAN MEDICAL BILL": "KOKILABEN DHIRUBHAI AMBANI HOSPITAL",
    "KOKILABEN HOSPITL": "KOKILABEN DHIRUBHAI AMBANI HOSPITAL",
    "KOKILABEN HOSP": "KOKILABEN DHIRUBHAI AMBANI HOSPITAL",
    "KOKILABEN HOSPITAL": "KOKILABEN DHIRUBHAI AMBANI HOSPITAL"
}
 
# -------------------------------
# Convert first page to high-quality image
# -------------------------------
def get_first_page_image(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
 
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
 
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.grayscale(img)
    img = img.point(lambda x: 0 if x < 128 else 255, '1')  # binarize
    img = img.filter(ImageFilter.SHARPEN)
 
    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()
 
# -------------------------------
# Simple fuzzy match using difflib
# -------------------------------
def fuzzy_match(text, vendor_list, cutoff=0.7):
    matches = get_close_matches(text, vendor_list, n=1, cutoff=cutoff)
    if matches:
        return matches[0]
    return None
 
# -------------------------------
# Detect vendor
# -------------------------------
def detect_vendor(lines):
    lines_upper = [l.upper().strip() for l in lines if l.strip()]
 
    # Apply corrections first
    lines_upper = [corrections.get(l, l) for l in lines_upper]
 
    # Scan top 25 lines
    for line in lines_upper[:25]:
        # Ride apps
        match = fuzzy_match(line, ride_vendors)
        if match:
            return match
       
        # Hotels
        match = fuzzy_match(line, hotel_vendors)
        if match:
            return match
       
        # Hospitals
        match = fuzzy_match(line, hospital_vendors)
        if match:
            return match
 
    # Fallback: first readable line
    for line in lines_upper[:10]:
        if re.match(r"^[A-Za-z .&'-]{3,}$", line):
            return line.title()
 
    return "Vendor Not Found"
 
# -------------------------------
# Master function
# -------------------------------
def get_vendor(pdf_path):
    img_data = get_first_page_image(pdf_path)
    reader = easyocr.Reader(['en'])
    lines = reader.readtext(img_data, detail=0)
    lines = [l.strip() for l in lines if l.strip()]
    if not lines:
        return "Vendor Not Found"
    return detect_vendor(lines)
 
# -------------------------------
# Test your files
# -------------------------------
pdf_files = [
        # "bills_folder/1405_21752024105948482.pdf",
        # "bills_folder/1505_1175202411044555.pdf",
        # "bills_folder/13051752024105712915.pdf",
        # "bills_folder/invoice-4059842024232149839.pdf",
        # "bills_folder/ketan-medicalbill1052024211446776.pdf",
        # "bills_folder/march25to27742024233659598.pdf",
        # "bills_folder/mobileinvoice1842024104420407.pdf",
        # "bills_folder/receipt_01apr2024_81310420249204721.pdf",
        # "bills_folder/receipt_01apr2024_740104202492111850.pdf",
        # "bills_folder/rupali-medicalbill105202421167943.pdf",
        # "bills_folder/uber2542024182742481.pdf",
        # "bills_folder/uber-12542024182912518.pdf",
        # "bills_folder/uber-22542024183027431.pdf",
        # "bills_folder/uber-32542024183132308.pdf",
        # "bills_folder/uber-42542024183234139.pdf",
        # "bills_folder/uber-52542024183425202.pdf",
        # "bills_folder/Screenshot 2025-10-09 174619.png"
        # "bills_folder/ketan-medicalbill1052024211446776.pdf"
]
 
for pdf in pdf_files:
    print(pdf, "→", get_vendor(pdf))