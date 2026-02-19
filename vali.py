import os
import hashlib
import boto3
import pandas as pd
from decimal import Decimal
from datetime import datetime

from date import extract_date_from_text
from total import extract_total, extract_text_full
from invoice import extract_invoice, check_known_invoice_in_text
from ven1 import get_vendor


# -------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------
DYNAMO_REGION = "ap-south-1"
DYNAMO_TABLE = "claimed_invoice"


# -------------------------------------------------------------
# FILE HASH
# -------------------------------------------------------------
def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def normalize_date(date_val):
    try:
        dt = pd.to_datetime(date_val, errors="coerce")
        return dt.strftime("%d-%m-%Y") if not pd.isna(dt) else None
    except Exception:
        return None


def total_within_range(extracted, known):
    try:
        extracted = float(extracted)
        known = float(known)
        return (known - 5) <= extracted <= (known + 5)
    except Exception:
        return False


# -------------------------------------------------------------
# DYNAMODB HELPERS
# -------------------------------------------------------------
def get_dynamo_table():
    dynamodb = boto3.resource("dynamodb", region_name=DYNAMO_REGION)
    return dynamodb.Table(DYNAMO_TABLE)


from botocore.exceptions import ClientError

def is_duplicate_file_hash(table, file_hash):
    try:
        response = table.get_item(
            Key={
                "File_Hash": file_hash
            },
            ProjectionExpression="File_Hash"  # faster, cheaper
        )
        return "Item" in response

    except ClientError as e:
        # Log this in real apps
        print("DynamoDB GetItem error:", e)
        return False


def is_duplicate_claim(table, invoice_no, extracted_total, claim_type):
    try:
        extracted_total = float(extracted_total)
    except Exception:
        return False

    response = table.scan(
        FilterExpression="Invoice_Number = :inv AND Claim_Type = :ct",
        ExpressionAttributeValues={
            ":inv": invoice_no,
            ":ct": claim_type
        }
    )

    for item in response.get("Items", []):
        try:
            db_total = float(item.get("Total_Amount", 0))
            if abs(db_total - extracted_total) <= 5:
                return True
        except Exception:
            continue

    return False


# -------------------------------------------------------------
# MAIN PROCESS
# -------------------------------------------------------------
def process_invoice(file_path, known_date, known_total, claim_type,emp_code):
    table = get_dynamo_table()

    file_name = os.path.basename(file_path)
    file_hash = get_file_hash(file_path)

    # -------------------------------------------------
    # HARD DUPLICATE (File Hash)
    # -------------------------------------------------
    if is_duplicate_file_hash(table, file_hash):
        return {
            "status": "DUPLICATE_CLAIM",
            "reason": "File already processed",
            "file_hash": file_hash,
	    "invoice_number":None,
	    "invoice_date" : None,
    	    "vendor" : None,
	    "total_amount":None,
    	    "mismatched_fields":[]
        }

    # -------------------------------------------------
    # OCR
    # -------------------------------------------------
    text = extract_text_full(file_path)
    invoice_date = extract_date_from_text(text)
    extracted_invoice = extract_invoice(text)
    vendor = get_vendor(file_path)
    total = extract_total(text)

    # -------------------------------------------------
    # Known invoice fallback
    # -------------------------------------------------
    KNOWN_INVOICE_NUMBER = "MH01CR1759"
    known_present = check_known_invoice_in_text(text, KNOWN_INVOICE_NUMBER)

    if extracted_invoice in ["NA", "Not Found", None, "", "Invoice Not Found"] and known_present:
        invoice_no = KNOWN_INVOICE_NUMBER
    else:
        invoice_no = extracted_invoice

    # -------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------
    extracted_date_norm = normalize_date(invoice_date)
    known_date_norm = normalize_date(known_date)

    date_match = extracted_date_norm == known_date_norm
    total_match = total_within_range(total, known_total)

    dynamo_duplicate = is_duplicate_claim(
        table,
        invoice_no,
        total,
        claim_type
    )

    mismatched_fields = []
    if not date_match:
        mismatched_fields.append("invoice_date")
    if not total_match:
        mismatched_fields.append("total_amount")

    if dynamo_duplicate:
        status = "DUPLICATE_CLAIM"
    elif mismatched_fields:
        status = "MISMATCHED_VALUE"
    else:
        status = "NEW_CLAIM"

    # -------------------------------------------------
    # SAVE ONLY NEW CLAIM
    # -------------------------------------------------
    if status == "NEW_CLAIM":
        table.put_item(
            Item={
                "File_Hash": file_hash,                  # Partition Key
                "Invoice_Number": invoice_no,            # Sort Key (if enabled)
                "File_Name": file_name,
                "Invoice_Date": invoice_date,
                "Vendor": vendor,
                "Total_Amount":Decimal(str(float(total))) if total else None,
                "Claim_Type": claim_type,
                "String_Extracted": text,
		"emp_code":emp_code,
                "Created_At": datetime.utcnow().isoformat()
            }
        )

        print("NEW_CLAIM inserted into DynamoDB")

    # -------------------------------------------------
    # FINAL RESPONSE
    # -------------------------------------------------
    return {
        "status": status,
        "invoice_number": invoice_no,
        "invoice_date": invoice_date,
        "total_amount": float(total) if total else None,
        "vendor": vendor,
        "mismatched_fields": mismatched_fields
    }
