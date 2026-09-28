import os
import base64
import uuid
import pandas as pd
from flask import Flask, request, jsonify
from dateutil import parser
import boto3
from decimal import Decimal


# ============================================================
# DYNAMODB SETUP
# ============================================================

dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1"
)

table = dynamodb.Table("CLAIM-DATA")


# ============================================================
# USER AUTH
# ============================================================

VALID_USERNAME = "UATUser"
VALID_PASSWORD = "Admin"


# ============================================================
# EXTERNAL EXTRACTORS
# ============================================================

from total import extract_total, extract_text_full
from invoice import extract_invoice
from date import extract_date_from_text


# ============================================================
# DATE NORMALIZER
# ============================================================

def normalize_date(date_str):

    if not date_str:
        return None

    try:
        return parser.parse(
            str(date_str),
            dayfirst=True
        ).date()

    except Exception:
        return None


# ============================================================
# BASE64 DECODER
# ============================================================

def decode_base64_file(base64_string):

    if not base64_string:
        raise ValueError("base64File is missing")

    if "base64," in base64_string:
        base64_string = base64_string.split("base64,", 1)[1]

    file_bytes = base64.b64decode(
        base64_string.strip()
    )

    os.makedirs(
        "temp_files",
        exist_ok=True
    )

    if file_bytes.startswith(b"%PDF"):

        ext = ".pdf"

    elif file_bytes[:2] == b"PK":

        ext = ".xlsx"

    else:

        ext = ".jpg"

    path = os.path.join(
        "temp_files",
        f"{uuid.uuid4()}{ext}"
    )

    with open(path, "wb") as f:
        f.write(file_bytes)

    return path


# ============================================================
# DUPLICATE CHECK
# ============================================================

def check_duplicate(df, emp, inv, date, amt):

    if df.empty:
        return False

    required_columns = [
        "Employee_Code",
        "Invoice_No",
        "Date",
        "Total_Amount"
    ]

    for col in required_columns:

        if col not in df.columns:
            return False

    dup = df[
        (df["Employee_Code"] == emp) &
        (df["Invoice_No"] == inv) &
        (df["Date"] == date) &
        (abs(
            pd.to_numeric(
                df["Total_Amount"],
                errors="coerce"
            ) - amt
        ) <= 5)
    ]

    return not dup.empty


# ============================================================
# SAVE TO EXCEL
# ============================================================

def insert_into_excel(records):

    DB = "claim.xlsx"

    if os.path.exists(DB):

        df = pd.read_excel(DB)

    else:

        df = pd.DataFrame(
            columns=[
                "hash",
                "Employee_Code",
                "Invoice_No",
                "Date",
                "Total_Amount",
                "Claim_Type",
                "Claim_ID",
                "Status",
                "Remark"
            ]
        )

    df = pd.concat(
        [
            df,
            pd.DataFrame(records)
        ],
        ignore_index=True
    )

    df.to_excel(
        DB,
        index=False
    )


# ============================================================
# SAVE TO DYNAMODB
#
# IMPORTANT:
# DynamoDB partition key = hash
# ============================================================

def insert_into_dynamodb(records):

    for rec in records:

        # hash is mandatory because it is the
        # DynamoDB partition key.

        hash_value = rec.get("hash")

        if not hash_value:
            raise ValueError(
                "DynamoDB partition key 'hash' is missing"
            )

        item = {
            "hash": str(hash_value),

            "Claim_ID": str(
                rec.get("Claim_ID", "")
            ),

            "Invoice_No": str(
                rec.get("Invoice_No", "")
            ),

            "Employee_Code": str(
                rec.get("Employee_Code", "")
            ),

            "Date": str(
                rec.get("Date", "")
            ),

            "Claim_Type": str(
                rec.get("Claim_Type", "")
            ),

            "Status": str(
                rec.get("Status", "")
            ),

            "Total_Amount": Decimal(
                str(rec.get("Total_Amount", 0))
            ),

            "Remark": str(
                rec.get("Remark", "")
            )
        }

        table.put_item(
            Item=item
        )


# ============================================================
# DAILY EXPENSE
# ============================================================

def process_daily_expense_excel(
    path,
    emp,
    ctype,
    voucher,
    db_df,
    c_id,
    hash_value,
    remark
):

    df = pd.read_excel(path)

    required_cols = [
        "Invoice_No",
        "Date",
        "Total_Amount"
    ]

    for col in required_cols:

        if col not in df.columns:

            return {
                "status": "ERROR",
                "message": f"{col} column missing in Excel"
            }

    daily_limit = float(
        voucher.get(
            "Daily_Limit",
            0
        )
    )

    voucher_amount = float(
        voucher.get(
            "Bill_Amount",
            0
        )
    )

    total_excel_amount = 0

    records = []

    for _, row in df.iterrows():

        inv = str(
            row["Invoice_No"]
        )

        date_obj = normalize_date(
            row["Date"]
        )

        amt = float(
            row["Total_Amount"]
        )

        if check_duplicate(
            db_df,
            emp,
            inv,
            str(date_obj),
            amt
        ):

            return {
                "status": "DUPLICATE_CLAIM",
                "invoice_number": inv
            }

        total_excel_amount += amt

        records.append({

            "hash": str(hash_value),

            "Employee_Code": emp,

            "Invoice_No": inv,

            "Date": str(date_obj),

            "Total_Amount": amt,

            "Claim_Type": ctype,

            "Claim_ID": c_id,

            "Status": "Approved",

            "Remark": remark
        })

    if total_excel_amount > voucher_amount:

        return {
            "status": "VOUCHER_AMOUNT_EXCEEDED",
            "excel_total": total_excel_amount,
            "voucher_amount": voucher_amount
        }

    return {
        "records": records,
        "total": total_excel_amount
    }


# ============================================================
# CLAIM PROCESSOR
# ============================================================

def process_claim(data):

    claim = data.get(
        "Claim",
        {}
    )

    emp = claim.get(
        "Employee_Code"
    )

    c_id = claim.get(
        "Claim_ID"
    )

    total_expected = float(
        claim.get(
            "Total_Bill_Amount",
            0
        )
    )

    remark = claim.get(
        "Remark",
        ""
    )

    # --------------------------------------------------------
    # DynamoDB HASH / PARTITION KEY
    # --------------------------------------------------------
    #
    # If hash is provided in request, use it.
    #
    # Otherwise generate a unique hash.
    #
    # IMPORTANT:
    # If your business requirement says hash must come
    # from a specific field, replace this logic accordingly.
    # --------------------------------------------------------

    hash_value = claim.get(
        "hash"
    )

    if not hash_value:

        hash_value = str(
            uuid.uuid4()
        )

    vouchers = claim.get(
        "Vouchers",
        []
    )

    if os.path.exists("claim.xlsx"):

        db_df = pd.read_excel(
            "claim.xlsx"
        )

    else:

        db_df = pd.DataFrame()

    grand_total = 0

    all_records = []

    for v in vouchers:

        subtype = v.get(
            "Sub_Type"
        )

        ctype = v.get(
            "Sub_Type"
        )

        voucher_total = 0

        attachments = v.get(
            "Attachments",
            []
        )

        if not attachments:
            continue

        for att in attachments:

            path = decode_base64_file(
                att.get("base64File")
            )

            # =================================================
            # DAILY EXPENSE
            # =================================================

            if subtype == "Daily_Expense":

                if not path.endswith(".xlsx"):

                    return {
                        "status": "INVALID_ATTACHMENT",
                        "message":
                            "Daily_Expense requires Excel attachment"
                    }

                result = process_daily_expense_excel(
                    path,
                    emp,
                    ctype,
                    v,
                    db_df,
                    c_id,
                    hash_value,
                    remark
                )

                if (
                    "status" in result
                    and result["status"] != "OK"
                ):

                    return result

                all_records.extend(
                    result["records"]
                )

                voucher_total += result[
                    "total"
                ]

                continue

            # =================================================
            # INDIVIDUAL EXPENSE
            # =================================================

            if subtype == "Individual_Expense":

                if path.endswith(".xlsx"):

                    return {
                        "status": "INVALID_ATTACHMENT",
                        "message":
                            "Individual_Expense requires PDF or Image"
                    }

                text = extract_text_full(
                    path
                )

                inv = extract_invoice(
                    text
                )

                date_text = extract_date_from_text(
                    text
                )

                invoice_date = normalize_date(
                    date_text
                )

                total = float(
                    extract_total(text) or 0
                )

                if check_duplicate(
                    db_df,
                    emp,
                    inv,
                    str(invoice_date),
                    total
                ):

                    return {
                        "status": "DUPLICATE_CLAIM",
                        "invoice_number": inv
                    }

                voucher_total += total

                all_records.append({

                    "hash": str(hash_value),

                    "Employee_Code": emp,

                    "Invoice_No": inv,

                    "Date": str(invoice_date),

                    "Total_Amount": total,

                    "Claim_Type": ctype,

                    "Claim_ID": c_id,

                    "Status": "Approved",

                    "Remark": remark
                })

    grand_total += voucher_total

    if grand_total > total_expected:

        return {
            "status": "CLAIM_TOTAL_MISMATCH",
            "total_attachments_amount":
                grand_total
        }

    # =========================================================
    # SAVE DATA
    # =========================================================

    if all_records:

        insert_into_excel(
            all_records
        )

        insert_into_dynamodb(
            all_records
        )

    return {
        "status": "NEW_CLAIM",
        "records_saved": len(
            all_records
        ),
        "total_amount": grand_total,
        "hash": str(hash_value),
        "Claim_ID": str(c_id)
    }


# ============================================================
# REJECT / APPROVE CLAIM
# ============================================================

def reject_claim(body):

    claim_id = body.get(
        "Claim_ID"
    )

    updated_status = body.get(
        "Status"
    )

    # ========================================================
    # STATUS VALIDATION
    # ========================================================

    if not updated_status:

        return {
            "status": "ERROR",
            "message":
                "Status cannot be empty. "
                "Allowed values: Rejected, Approved"
        }

    allowed_status = [
        "Rejected",
        "Approved"
    ]

    if updated_status not in allowed_status:

        return {
            "status": "ERROR",
            "message":
                f"Invalid Status '{updated_status}'. "
                f"Allowed values: {allowed_status}"
        }

    # ========================================================
    # HASH
    #
    # Since hash is the DynamoDB partition key,
    # we first find the corresponding hash from Excel.
    # ========================================================

    hash_value = body.get(
        "hash"
    )

    DB = "claim.xlsx"

    if not os.path.exists(DB):

        return {
            "status": "ERROR",
            "message":
                "Database file not found"
        }

    df = pd.read_excel(
        DB
    )

    if "Claim_ID" not in df.columns:

        return {
            "status": "ERROR",
            "message":
                "Claim_ID column missing in database"
        }

    # ========================================================
    # FIND CLAIM
    # ========================================================

    mask = (
        df["Claim_ID"].astype(str)
        == str(claim_id)
    )

    if not mask.any():

        return {
            "status": "NOT_FOUND",
            "message":
                f"No records found for Claim_ID {claim_id}"
        }

    # ========================================================
    # FIND HASH
    # ========================================================

    if not hash_value:

        if "hash" not in df.columns:

            return {
                "status": "ERROR",
                "message":
                    "hash column missing in database"
            }

        hash_values = (
            df.loc[mask, "hash"]
            .dropna()
            .astype(str)
            .unique()
        )

        if len(hash_values) == 0:

            return {
                "status": "ERROR",
                "message":
                    f"No hash found for Claim_ID {claim_id}"
            }

        hash_value = hash_values[0]

    # ========================================================
    # UPDATE EXCEL
    # ========================================================

    df.loc[
        mask,
        "Status"
    ] = updated_status

    df.to_excel(
        DB,
        index=False
    )

    # ========================================================
    # UPDATE DYNAMODB
    #
    # IMPORTANT:
    # DynamoDB table uses:
    #
    # hash = Partition Key
    #
    # Therefore DO NOT use Claim_ID + Invoice_No here.
    # ========================================================

    updated_rows = 0

    for _, row in df[mask].iterrows():

        row_hash = str(
            row["hash"]
            if pd.notna(row["hash"])
            else hash_value
        )

        try:

            table.update_item(

                Key={
                    "hash": row_hash
                },

                UpdateExpression:
                    "SET #s = :val",

                ExpressionAttributeNames={
                    "#s": "Status"
                },

                ExpressionAttributeValues={
                    ":val": updated_status
                }
            )

            updated_rows += 1

        except Exception as e:

            return {
                "status": "ERROR",
                "message":
                    f"DynamoDB update failed: {str(e)}"
            }

    return {

        "status": "SUCCESS",

        "message":
            f"Claim {claim_id} "
            f"updated to {updated_status}",

        "rows_updated":
            updated_rows,

        "hash":
            str(hash_value)
    }


# ============================================================
# FLASK API
# ============================================================

app = Flask(__name__)


# ============================================================
# PROCESS INVOICE / CLAIM
# ============================================================

@app.route(
    "/process-invoice",
    methods=["POST"]
)
def api():

    # ========================================================
    # AUTH VALIDATION
    # ========================================================

    username = request.headers.get(
        "X-Username"
    )

    password = request.headers.get(
        "X-Password"
    )

    if not username or not password:

        return jsonify({
            "error":
                "Authentication headers missing"
        }), 401

    if (
        username != VALID_USERNAME
        or password != VALID_PASSWORD
    ):

        return jsonify({
            "error":
                "Invalid username or password"
        }), 401

    # ========================================================
    # PROCESS CLAIM
    # ========================================================

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "status": "ERROR",
                "message":
                    "Request body is empty"
            }), 400

        result = process_claim(
            data
        )

        return jsonify(
            result
        )

    except Exception as e:

        return jsonify({

            "status": "ERROR1",

            "message": str(e)

        }), 500


# ============================================================
# REJECT / APPROVE API
# ============================================================

@app.route(
    "/reject",
    methods=["POST"]
)
def reject_api():

    # ========================================================
    # AUTH VALIDATION
    # ========================================================

    username = request.headers.get(
        "X-Username"
    )

    password = request.headers.get(
        "X-Password"
    )

    if not username or not password:

        return jsonify({
            "error":
                "Authentication headers missing"
        }), 401

    if (
        username != VALID_USERNAME
        or password != VALID_PASSWORD
    ):

        return jsonify({
            "error":
                "Invalid username or password"
        }), 401

    # ========================================================
    # UPDATE CLAIM
    # ========================================================

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "status": "ERROR",
                "message":
                    "Request body is empty"
            }), 400

        result = reject_claim(
            data
        )

        return jsonify(
            result
        )

    except Exception as e:

        return jsonify({

            "status": "ERROR1",

            "message": str(e)

        }), 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )
