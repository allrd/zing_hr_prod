import pdfplumber
import re

def extract_vendor(text):
    text_clean = text.replace(",", "")

    # Common address/irrelevant words
    address_words = [
        "india", "karnataka", "maharashtra", "thane", "bengaluru", "mumbai",
        "road", "village", "taluka", "district", "dist", "pin", "pincode",
        "state", "west", "east", "south", "north"
    ]

    def is_not_address(line):
        return not any(w in line.lower() for w in address_words)

    # Known vendors/services to detect
    vendors = [
        "Uber", "Ola", "Flipkart", "Amazon", "Zomato", "Swiggy",
        "Dominos", "Makemytrip", "IRCTC", "Cleartrip", "Hotel", "Resort",
        "Restaurant", "Airbnb"
    ]

    # Scan first 20 lines for vendor keywords
    lines = text_clean.split("\n")[:20]
    for line in lines:
        if not is_not_address(line):
            continue
        for vendor in vendors:
            if vendor.lower() in line.lower():
                return vendor

    # Fallback: return first capitalized word line (likely vendor name)
    for line in lines:
        if not is_not_address(line):
            continue
        words = re.findall(r"[A-Z][a-zA-Z0-9& ]{2,}", line)
        if words:
            return words[0].strip()

    return "Vendor not found"


# Test PDF
pdf_path = "bills_folder/rupali-medicalbill105202421167943.pdf"
pdf = pdfplumber.open(pdf_path)

for i, page in enumerate(pdf.pages):
    print(f"\n===== PAGE {i+1} =====\n")
    text = page.extract_text()
    print(text)

    vendor_name = extract_vendor(text)
    print(f"\n>> Extracted Vendor: {vendor_name}")
