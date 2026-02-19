from flask import Flask, request, jsonify
from vali import process_invoice
from valiex import process_daily_expense_excel
import os
import base64
import uuid
import magic


app = Flask(__name__)

# -------------------------
# STATIC CREDENTIALS
# -------------------------
VALID_USERNAME = "UATUser"
VALID_PASSWORD = "Admin"

# -------------------------
# HELPER FUNCTIONS
# -------------------------
def get_extension(file_path):
    return os.path.splitext(file_path)[1].lower()

def normalize_claim_type(value):
    if not value:
        return ""
    return value.strip().lower()

# -------------------------
# TEST API
# -------------------------
@app.route("/process-invoice1", methods=["POST"])
def process_test():
    return "Success"

# -------------------------
# MAIN API
# -------------------------
@app.route("/process-invoice", methods=["POST"])
def process_invoice_api():

    # 1️⃣ AUTH HEADERS
    username = request.headers.get("X-Username")
    password = request.headers.get("X-Password")

    if not username or not password:
        return jsonify({"error": "Authentication headers missing"}), 401

    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return jsonify({"error": "Invalid username or password"}), 401

    # 2️⃣ REQUEST BODY
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    base64_string = data.get("base64File")
    claim_type_raw = data.get("claim_type")
    processed_by = data.get("processed_by", 101)
    limit = data.get("limit")
    emp_code = data.get("emp_code")
    known_date = data.get("known_date")
    known_total = data.get("known_total")
    if not base64_string:
        return jsonify({"error": "base64File is required"}), 400

    claim_type = normalize_claim_type(claim_type_raw)

    # 3️⃣ DECODE FILE
    try:
        file_bytes = base64.b64decode(base64_string)
    except Exception:
        return jsonify({"error": "Invalid base64 data"}), 400

    # TEMP FILE (extension decided later)
    temp_path = f"/tmp/{uuid.uuid4()}"
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    mime = magic.from_buffer(file_bytes, mime=True)

    if mime == "application/pdf":
        ext = ".pdf"
    elif mime == "image/png":
        ext = ".png"
    elif mime == "image/jpeg":
        ext = ".jpg"
    elif mime in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]:
        ext = ".xlsx"
    else:
        return jsonify({"error": "Unsupported file type"}), 400    


    #ext = get_extension(temp_path)

    # -------------------------
    # INDIVIDUAL EXPENSE
    # -------------------------
    if claim_type == "individual expense":

        if ext in [".xls", ".xlsx", ".csv"]:
            return jsonify({
                "status": "FAILED",
                "reason": "UNSUPPORTED_FILE_TYPE",
                "allowed_extensions": [".pdf", ".png", ".jpg", ".jpeg"]
            }), 400

        if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
            return jsonify({
                "status": "FAILED",
                "reason": "UNSUPPORTED_FILE_TYPE",
		"ExtType":f"{ext} filepath"
            }), 400

        file_path = f"{temp_path}{ext}"
        os.rename(temp_path, file_path)

     #   df = load_or_create_excel()
      #  before_count = len(df)

#        df = process_invoice(file_path, df,known_date, known_total, claim_type)
        result = process_invoice(
            file_path=file_path,
            known_date=known_date,
            known_total=known_total,
            claim_type="Individual Expense",
	    emp_code=emp_code
        )
        #after_count = len(df)
       # status = "NEW_CLAIM" if after_count > before_count else "DUPLICATE_CLAIM"
       # last_row = df.iloc[-1]

        return jsonify({
            "status": result["status"],
            "invoice_number": result["invoice_number"],
            "invoice_date": result["invoice_date"],
            "vendor": result["vendor"],
            "total_amount": result["total_amount"],
            "processed_by": processed_by,
            "mismatched_fields": result.get("mismatched_fields", [])
        })

    # -------------------------
    # DAILY EXPENSE
    # -------------------------
    elif claim_type == "daily expense":

        if ext not in [".xls", ".xlsx", ".csv"]:
            return jsonify({
                "status": "FAILED",
                "reason": "UNSUPPORTED_FILE_TYPE",
                "allowed_extensions": [".xls", ".xlsx", ".csv"]
            }), 400

        if limit is None:
            return jsonify({
                "status": "FAILED",
                "reason": "LIMIT_REQUIRED"
            }), 400

        file_path = f"{temp_path}{ext}"
        os.rename(temp_path, file_path)

        result = process_daily_expense_excel(file_path, limit)

        return jsonify({
            "status": result["status"],
            "reason": result.get("reason"),
            "total_amount": result.get("total_amount"),
            "total_records": result.get("total_records"),
            "processed_by": processed_by
        })

    # -------------------------
    # INVALID CLAIM TYPE
    # -------------------------
    else:
        return jsonify({
            "status": "FAILED",
            "reason": "INVALID_CLAIM_TYPE",
            "allowed_claim_types": ["Individual Expense", "Daily Expense"]
        }), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
