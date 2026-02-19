import os
import hashlib
import pandas as pd

from date import extract_date_from_text
from total import extract_total, extract_text_full
from invoice import extract_invoice, check_known_invoice_in_text
from ven1 import get_vendor

EXCEL_FILE = "claimed_invoices.xlsx"

REQUIRED_COLUMNS = [
    "File Name", "File Hash", "Invoice Date",
    "Invoice Number", "Vendor", "Total Amount", "String Extracted"
]

def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def load_or_create_excel():
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
    else:
        df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        df.to_excel(EXCEL_FILE, index=False)
    return df

def is_already_claimed(df, invoice_no, total):
    df["Invoice Number"] = df["Invoice Number"].astype(str).str.lower()
    df["Total Amount"] = df["Total Amount"].astype(str)
    return not df[
        (df["Invoice Number"] == str(invoice_no).lower()) &
        (df["Total Amount"] == str(total))
    ].empty

def process_invoice(file_path):
    df = load_or_create_excel()

    file_name = os.path.basename(file_path)
    file_hash = get_file_hash(file_path)

    if file_hash in df["File Hash"].astype(str).values:
        return {"status": "DUPLICATE_FILE"}

    text = extract_text_full(file_path)

    invoice_date = extract_date_from_text(text)
    extracted_invoice = extract_invoice(text)
    vendor = get_vendor(file_path)
    total = extract_total(text)

    invoice_no = extracted_invoice

    if is_already_claimed(df, invoice_no, total):
        return {
            "status": "DUPLICATE_CLAIM",
            "invoice_number": invoice_no,
            "invoice_date": invoice_date,
            "vendor": vendor,
            "total_amount": total
        }

    df.loc[len(df)] = [
        file_name, file_hash, invoice_date,
        invoice_no, vendor, total, text
    ]
    df.to_excel(EXCEL_FILE, index=False)

    return {
        "status": "NEW_CLAIM",
        "invoice_number": invoice_no,
        "invoice_date": invoice_date,
        "vendor": vendor,
        "total_amount": total
    }
