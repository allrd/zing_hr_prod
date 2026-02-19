import os
import hashlib
import pandas as pd

# 🔐 JWT
from jwt_token import create_jwt, verify_jwt

from date import extract_date_from_text
from total import extract_total, extract_text_full
from invoice import extract_invoice, check_known_invoice_in_text
from ven1 import get_vendor


EXCEL_FILE = "claimed_invoices.xlsx"

REQUIRED_COLUMNS = [
    "File Name",
    "File Hash",
    "Invoice Date",
    "Invoice Number",
    "Vendor",
    "Total Amount",
    "String Extracted"
]


# -------------------------------------------------------------
# FILE HASH (STRONG DUPLICATE PROTECTION)
# -------------------------------------------------------------
def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# -------------------------------------------------------------
# LOAD OR CREATE EXCEL (SAFE)
# -------------------------------------------------------------
def load_or_create_excel():

    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
    else:
        df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        df.to_excel(EXCEL_FILE, index=False)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


# -------------------------------------------------------------
# DUPLICATE CHECK (INVOICE + TOTAL)
# -------------------------------------------------------------
def is_already_claimed(df, invoice_no, total):

    invoice_no = str(invoice_no).strip().lower()
    total = str(total).strip()

    df["Invoice Number"] = df["Invoice Number"].astype(str).str.strip().str.lower()
    df["Total Amount"] = df["Total Amount"].astype(str).str.strip()

    match = df[
        (df["Invoice Number"] == invoice_no) &
        (df["Total Amount"] == total)
    ]

    return not match.empty


# -------------------------------------------------------------
# MAIN PROCESS
# -------------------------------------------------------------
def process_invoice(file_path, df):

    file_name = os.path.basename(file_path)
    file_hash = get_file_hash(file_path)

    if file_hash in df["File Hash"].astype(str).values:
        print(f"\n❌ ALREADY CLAIMED (FILE MATCH): {file_name}")
        return df

    text = extract_text_full(file_path)

    invoice_date = extract_date_from_text(text)
    extracted_invoice = extract_invoice(text)

    KNOWN_INVOICE_NUMBER = "MH01CR1759"
    known_present = check_known_invoice_in_text(text, KNOWN_INVOICE_NUMBER)

    if extracted_invoice in ["NA", "Not Found", None, "Invoice Not Found", ""] and known_present:
        invoice_no = KNOWN_INVOICE_NUMBER
    else:
        invoice_no = extracted_invoice

    vendor = get_vendor(file_path)
    total = extract_total(text)

    if is_already_claimed(df, invoice_no, total):
        print(f"\n❌ ALREADY CLAIMED: {file_name}")
        print("Invoice:", invoice_no)
        print("Total:", total)
        return df

    print(f"\n✅ NEW CLAIM: {file_name}")

    new_row = {
        "File Name": file_name,
        "File Hash": file_hash,
        "Invoice Date": invoice_date,
        "Invoice Number": invoice_no,
        "Vendor": vendor,
        "Total Amount": total,
        "String Extracted": text
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

    return df


# -------------------------------------------------------------
# MULTI FILE HANDLER (JWT PROTECTED)
# -------------------------------------------------------------
def process_files(file_paths, jwt_token):   # 🔐 JWT added

    # 🔐 JWT VALIDATION (GATE)
    try:
        decoded = verify_jwt(jwt_token)
        print("🔐 JWT verified for user:", decoded)
    except Exception as e:
        print(f"\n❌ JWT ERROR: {e}")
        return

    df = load_or_create_excel()

    for path in file_paths:
        if os.path.exists(path):
            df = process_invoice(path, df)
        else:
            print(f"\n⚠️ File not found: {path}")


# -------------------------------------------------------------
# RUN
# -------------------------------------------------------------
if __name__ == "__main__":

    files = [
        #"bills_folder/uber254202418274248.pdf",
        "bills_folder/invoice-4059842024232149839.pdf"
    ]

    # SAMPLE JWT (from API / header)
    payload = {
        "user_id": 101,
        "role": "Admin"
    }

    jwt_token = create_jwt(payload)

    print("\n🔐 GENERATED JWT TOKEN:\n")
    print(jwt_token)

    process_files(files, jwt_token)