import os
import base64
import uuid
import pandas as pd
from flask import Flask, request, jsonify
from dateutil import parser
import boto3
from decimal import Decimal
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

# ================= DYNAMODB SETUP =================
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("CLAIM-DATA")

# ================= USER AUTH =================
VALID_USERNAME = "UATUser"
VALID_PASSWORD = "Admin"

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


# ================= CURRENT TIMESTAMP =================
def get_current_timestamp():
    return datetime.now(timezone.utc).isoformat()


# ================= BASE64 DECODER =================
def decode_base64_file(base64_string):

    if not base64_string:
        raise ValueError("Attachment base64 missing")

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
def check_duplicate(emp, inv, date, amt):

    response = table.scan(
        FilterExpression="Employee_Code = :emp AND Invoice_No = :inv AND #d = :date AND #s = :status",
        ExpressionAttributeNames={"#d": "Date", "#s": "Status"},
        ExpressionAttributeValues={
            ":emp": emp,
            ":inv": inv,
            ":date": date,
            ":status": "Approved"
        }
    )

    items = response.get("Items", [])

    for item in items:
        existing_amount = float(item.get("Total_Amount", 0))

        if abs(existing_amount - amt) <= 5:
            return True

    return False


# ================= SAVE TO EXCEL =================
def insert_into_excel(records):

    DB = "claim.xlsx"

    if os.path.exists(DB):
        df = pd.read_excel(DB)
    else:
        df = pd.DataFrame(columns=[
            "HASH",
            "Employee_Code",
            "Invoice_No",
            "Date",
            "Total_Amount",
            "Claim_Type",
            "Claim_ID",
            "Status",
            "Remark"
        ])

    df = pd.concat([df, pd.DataFrame(records)], ignore_index=True)
    df.to_excel(DB, index=False)


# ================= SAVE TO DYNAMODB =================
def insert_into_dynamodb(records):

    with table.batch_writer() as batch:

        for rec in records:

            current_time = get_current_timestamp()

            item = {
                "HASH": rec["HASH"],
                "Claim_ID": str(rec["Claim_ID"]),
                "Invoice_No": str(rec["Invoice_No"]),
                "Employee_Code": str(rec["Employee_Code"]),
                "Date": str(rec["Date"]),
                "Claim_Type": str(rec["Claim_Type"]),
                "Status": str(rec["Status"]),
                "Remark": str(rec.get("Remark", "")),
                "Total_Amount": Decimal(str(rec["Total_Amount"])),
                "Created_Time": current_time,
                "Modified_Time": current_time
            }

            batch.put_item(Item=item)


# ================= DAILY EXPENSE =================
def process_daily_expense_excel(path, emp, ctype, voucher, db_df, c_id):

    df = pd.read_excel(path)

    required_cols = ["Invoice_No", "Date", "Total_Amount"]

    for col in required_cols:
        if col not in df.columns:
            return {"code":1,"claim_id":c_id,"status": "ERROR", "message": f"{col} column missing in Excel"}

    voucher_amount = float(voucher.get("Bill_Amount", 0))

    total_excel_amount = 0
    records = []

    for _, row in df.iterrows():

        inv = str(row["Invoice_No"])
        date_obj = normalize_date(row["Date"])
        amt = float(row["Total_Amount"])

        if check_duplicate(emp, inv, str(date_obj), amt):
            return {
                "code": 1,
                "status": "DUPLICATE_CLAIM",
                "message": f"A duplicate claim was detected for invoice '{inv}'.",
                "data": {
                    "claim_id": c_id,
                    "invoice_number": inv
                },
                "errors": []
            }

        total_excel_amount += amt

        records.append({
            "HASH": str(uuid.uuid4()),
            "Employee_Code": emp,
            "Invoice_No": inv,
            "Date": str(date_obj),
            "Total_Amount": amt,
            "Claim_Type": ctype,
            "Claim_ID": c_id,
            "Status": "Approved",
            "Remark": "test"
        })

    if total_excel_amount > voucher_amount:
        return {
            "code": 1,
            "status": "VOUCHER_AMOUNT_EXCEEDED",
            "message": "Excel total exceeds the voucher amount.",
            "data": {
                "claim_id": c_id,
                "excel_total": total_excel_amount,
                "voucher_amount": voucher_amount
            },
            "errors": []
        }

    return {"code":0,"claim_id":c_id,"records": records, "total": total_excel_amount}


# ================= CLAIM PROCESSOR =================
def process_claim(data):

    claim = data.get("Claim", {})
    emp = claim.get("Employee_Code")
    c_id = claim.get("Claim_ID")

    if not c_id:
        return {
            "code": 1,
            "status": "VALIDATION_ERROR",
            "message": "Claim_ID is required.",
            "data": {},
            "errors": ["Missing required field: Claim_ID"]
        }

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

        for att in attachments:

            path = decode_base64_file(att.get("base64File"))

            try:

                # ================= DAILY EXPENSE =================
                if subtype == "Daily_Expense":

                    if not path.endswith(".xlsx"):
                        return {
                            "code": 1,
                            "status": "INVALID_ATTACHMENT",
                            "message": "Invalid attachment type provided.",
                            "data": {
                                "claim_id": c_id,
                                "expected": "Excel for Daily Expense / PDF or Image for Individual Expense"
                            },
                            "errors": []
                        }

                    result = process_daily_expense_excel(
                        path, emp, ctype, v, db_df, c_id
                    )

                    if "status" in result and result["status"] != "OK":
                        return result

                    all_records.extend(result["records"])
                    voucher_total += result["total"]

                # ================= INDIVIDUAL EXPENSE =================
                elif subtype == "Individual_Expense":

                    if path.endswith(".xlsx"):
                        return {
                            "code": 1,
                            "status": "INVALID_ATTACHMENT",
                            "message": "Invalid attachment type provided.",
                            "data": {
                                "claim_id": c_id,
                                "expected": "Excel for Daily Expense / PDF or Image for Individual Expense"
                            },
                            "errors": []
                        }

                    text = extract_text_full(path)

                    inv = extract_invoice(text)
                    date_text = extract_date_from_text(text)
                    invoice_date = normalize_date(date_text)
                    total = float(extract_total(text) or 0)

                    if check_duplicate(emp, inv, str(invoice_date), total):
                        return {
                            "code": 1,
                            "status": "DUPLICATE_CLAIM",
                            "message": f"A duplicate claim was detected for invoice '{inv}'.",
                            "data": {
                                "claim_id": c_id,
                                "invoice_number": inv
                            },
                            "errors": []
                        } 

                    voucher_total += total
                    voucher_amount = float(v.get("Bill_Amount", 0))
                    if voucher_total > voucher_amount:
                        return {
                            "code": 1,
                            "status": "VOUCHER_AMOUNT_EXCEEDED",
                            "message": "Total exceeds the voucher amount.",
                            "data": {
                                "claim_id": c_id,
                                "attachment_Total": voucher_total,
                                "voucher_amount": voucher_amount
                            },
                            "errors": []
                        }
                        

                    all_records.append({
                        "HASH": str(uuid.uuid4()),
                        "Employee_Code": emp,
                        "Invoice_No": inv,
                        "Date": str(invoice_date),
                        "Total_Amount": total,
                        "Claim_Type": ctype,
                        "Claim_ID": c_id,
                        "Status": "Approved",
                        "Remark": "test"
                    })

            finally:
                if os.path.exists(path):
                    os.remove(path)

        grand_total += voucher_total

    if grand_total > total_expected:
        return {
            "code": 1,
            "status": "CLAIM_TOTAL_MISMATCH",
            "message": "The total amount of attachments exceeds the declared claim amount.",
            "data": {
                "claim_id": c_id,
                "attachments_total": grand_total,
                "expected_total": total_expected
            },
            "errors": []
        }

    insert_into_excel(all_records)
    insert_into_dynamodb(all_records)

    return {
        "code": 0,
        "status": "SUCCESS",
        "message": "Claim processed successfully.",
        "data": {
            "claim_id": c_id,
            "records_saved": len(all_records),
            "total_amount": grand_total
        },
        "errors": []
    }


# ================= STATUS UPDATE =================

def reject_claim(body):

    claim_id = body.get("Claim_ID")
    updated_status = str(body.get("Status", "")).capitalize()

    allowed_status = ["Rejected", "Approved"]

    if not claim_id:
        return {
            "code": 1,
            "status": "VALIDATION_ERROR",
            "message": "Claim_ID is required.",
            "data": {},
            "errors": ["Missing required field: Claim_ID"]
        }

    if updated_status not in allowed_status:
        return {
            "code": 1,
            "status": "VALIDATION_ERROR",
            "message": "Claim_ID is required.",
            "data": {
                "claim_id": claim_id
            },
            "errors": [f"Invalid Status '{updated_status}'. Allowed values: {allowed_status}"]
        }

    # ================= FIND RECORDS IN DYNAMODB =================
    response = table.scan(
        FilterExpression=Attr("Claim_ID").eq(str(claim_id))
    )

    items = response.get("Items", [])

    if not items:
        return {
            "code": 1,
            "status": "NOT_FOUND",
            "message": "No records found for the given claim ID.",
            "data": {
                "claim_id": claim_id
            },
            "errors": []
        }

    rows_updated = 0

    # ================= UPDATE STATUS =================
    for item in items:

        try:
            table.update_item(
                Key={"HASH": item["HASH"]},
                UpdateExpression="SET #s = :val, Modified_Time = :m",
                ExpressionAttributeNames={"#s": "Status"},
                ExpressionAttributeValues={
                    ":val": updated_status,
                    ":m": get_current_timestamp()
                }
            )

            rows_updated += 1

        except ClientError as e:
            print(e.response["Error"]["Message"])

    return {
        "code": 0,
        "status": "SUCCESS",
        "message": f"Claim '{claim_id}' has been successfully updated to '{updated_status}'.",
        "data": {
            "claim_id": claim_id,
            "rows_updated": rows_updated,
            "updated_status": updated_status
        },
        "errors": []
    }

# ================= FLASK API =================
app = Flask(__name__)


@app.route("/process-invoice", methods=["POST"])
def api():

    username = request.headers.get("X-Username")
    password = request.headers.get("X-Password")

    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return jsonify({"code":1,"error": "Invalid username or password"}), 401

    try:
        return jsonify(process_claim(request.get_json()))
    except Exception as e:
        return jsonify({"code":1,"status": "ERROR1", "message": str(e)})


@app.route("/status-update", methods=["POST"])
def reject_api():

    username = request.headers.get("X-Username")
    password = request.headers.get("X-Password")

    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return jsonify({"code":1,"error": "Invalid username or password"}), 401

    try:
        return jsonify(reject_claim(request.get_json()))
    except Exception as e:
        return jsonify({"code":1,"status": "ERROR1", "message": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
