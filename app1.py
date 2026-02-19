import os
import base64
import uuid
import pandas as pd
from flask import Flask, request, jsonify
from dateutil import parser
 
# external extractors
from total import extract_total, extract_text_full
from invoice import extract_invoice
from date import extract_date_from_text
 
# ================= DATE NORMALIZER =================
def normalize_date(date_str):
    if not date_str:
        return None
    try:
        return parser.parse(str(date_str), dayfirst=True).date()
    except:
        return None
 
# ================= BASE64 DECODER =================
def decode_base64_file(base64_string):
    if "base64," in base64_string:
        base64_string = base64_string.split("base64,")[1]
 
    file_bytes = base64.b64decode(base64_string.strip())
 
    os.makedirs("temp_files", exist_ok=True)
 
    if file_bytes.startswith(b"%PDF"):
        ext = ".pdf"
    elif file_bytes[:2] == b"PK":
        ext = ".xlsx"
    else:
        ext = ".jpg"
 
    path = os.path.join("temp_files", f"{uuid.uuid4()}{ext}")
 
    with open(path, "wb") as f:
        f.write(file_bytes)
 
    return path
 
# ================= DUPLICATE CHECK =================
def check_duplicate(df, emp, inv, date, amt):
    if df.empty:
        return False
 
    dup = df[
        (df["Employee_Code"] == emp) &
        (df["Invoice_No"] == inv) &
        (df["Date"] == date) &
        (abs(df["Total_Amount"] - amt) <= 5)
    ]
    return not dup.empty
 
# ================= SAVE TO EXCEL =================
def insert_into_excel(records):
    DB = "claim.xlsx"
 
    if os.path.exists(DB):
        df = pd.read_excel(DB)
    else:
        df = pd.DataFrame(columns=[
            "Employee_Code",
            "Invoice_No",
            "Date",
            "Total_Amount",
            "Claim_Type"
        ])
 
    df = pd.concat([df, pd.DataFrame(records)], ignore_index=True)
    df.to_excel(DB, index=False)
 
# ================= DAILY EXPENSE (EXCEL) =================
def process_daily_expense_excel(path, emp, ctype, voucher, db_df):
    df = pd.read_excel(path)
 
    required_cols = ["Invoice_No", "Date", "Total_Amount"]
    for col in required_cols:
        if col not in df.columns:
            return {"status": "ERROR", "message": f"{col} column missing in Excel"}
 
    daily_limit = float(voucher.get("Daily_Limit", 0))
    voucher_amount = float(voucher.get("Bill_Amount", 0))
 
    total_excel_amount = 0
    records = []
 
    for _, row in df.iterrows():
        inv = str(row["Invoice_No"])
        date_obj = normalize_date(row["Date"])
        amt = float(row["Total_Amount"])
 
        # I️⃣ duplicate check
        if check_duplicate(db_df, emp, inv, str(date_obj), amt):
            return {
                "status": "DUPLICATE_CLAIM",
                "invoice_number": inv
            }
 
        # II️⃣ daily limit check
        if amt > daily_limit:
            return {
                "status": "DAILY_LIMIT_EXCEEDED",
                "invoice_number": inv,
                "amount": amt,
                "daily_limit": daily_limit
            }
 
        total_excel_amount += amt
 
        records.append({
            "Employee_Code": emp,
            "Invoice_No": inv,
            "Date": str(date_obj),
            "Total_Amount": amt,
            "Claim_Type": ctype
        })
 
    # III️⃣ total <= voucher bill amount
    if total_excel_amount > voucher_amount:
        return {
            "status": "VOUCHER_AMOUNT_EXCEEDED",
            "excel_total": total_excel_amount,
            "voucher_amount": voucher_amount
        }
 
    return {"records": records, "total": total_excel_amount}
 
# ================= CLAIM PROCESSOR =================
def process_claim(data):
 
    claim = data.get("Claim", {})
    emp = claim.get("Employee_Code")
    #ctype = claim.get("Claim_Type")
    total_expected = float(claim.get("Total_Bill_Amount", 0))
 
    vouchers = claim.get("Vouchers", [])
    db_df = pd.read_excel("claim.xlsx") if os.path.exists("claim.xlsx") else pd.DataFrame()
 
    grand_total = 0
    all_records = []
 
    for v in vouchers:
 
        subtype = v.get("Sub_Type")
        ctype = v.get("Sub_Type")
        voucher_total = 0
 
        attachments = v.get("Attachments", [])
        if not attachments:
            continue
 
        for att in attachments:
 
            path = decode_base64_file(att.get("base64File"))
 
            # =====================================================
            # DAILY EXPENSE → ONLY EXCEL
            # =====================================================
            if subtype == "Daily_Expense":
 
                if not path.endswith(".xlsx"):
                    return {
                        "status": "INVALID_ATTACHMENT",
                        "message": "Daily_Expense requires Excel attachment"
                    }
 
                result = process_daily_expense_excel(
                    path, emp, ctype, v, db_df
                )
 
                if "status" in result and result["status"] != "OK":
                    return result
 
                all_records.extend(result["records"])
                voucher_total += result["total"]
                continue
 
            # =====================================================
            # INDIVIDUAL EXPENSE → PDF / IMAGE
            # =====================================================
            if subtype == "Individual_Expense":
 
                if path.endswith(".xlsx"):
                    return {
                        "status": "INVALID_ATTACHMENT",
                        "message": "Individual_Expense requires PDF or Image"
                    }
 
                text = extract_text_full(path)
 
                inv = extract_invoice(text)
                date_text = extract_date_from_text(text)
                invoice_date = normalize_date(date_text)
                total = float(extract_total(text) or 0)
 
                if check_duplicate(db_df, emp, inv, str(invoice_date), total):
                    return {
                        "status": "DUPLICATE_CLAIM",
                        "invoice_number": inv
                    }
 
                voucher_total += total
 
                all_records.append({
                    "Employee_Code": emp,
                    "Invoice_No": inv,
                    "Date": str(invoice_date),
                    "Total_Amount": total,
                    "Claim_Type": ctype
                })
 
        grand_total += voucher_total
 
    # final claim validation
    if grand_total > total_expected:
        return {
            "status": "CLAIM_TOTAL_MISMATCH",
            "total_attachments_amount": grand_total
        }
 
    insert_into_excel(all_records)
 
    return {
        "status": "NEW_CLAIM",
        "records_saved": len(all_records),
        "total_amount": grand_total
    }
 
# ================= FLASK API =================
app = Flask(__name__)
 
@app.route("/process-invoice", methods=["POST"])
def api():
    try:
        return jsonify(process_claim(request.get_json()))
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})
 
if __name__ == "__main__":
    app.run(debug=True)
 
