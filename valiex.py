import pandas as pd
import numpy as np
import os

EXCEL_DB = "expenses_database.xlsx"

def process_daily_expense_excel(file_path, daily_limit, uploaded_by="SYSTEM"):

    # -------------------------

    # 1. FILE CHECK

    # -------------------------

    if not file_path.lower().endswith((".xls", ".xlsx")):

        return {"status": "FAILED", "reason": "UNSUPPORTED_FILE_TYPE"}



    if not os.path.exists(file_path):

        return {"status": "FAILED", "reason": "FILE_NOT_FOUND"}



    # -------------------------

    # 2. READ EXCEL

    # -------------------------

    try:

        df = pd.read_excel(file_path)

    except Exception:

        return {"status": "FAILED", "reason": "INVALID_EXCEL_FILE"}



    df.columns = [str(c).strip() for c in df.columns]



    # -------------------------

    # 3. AUTO-DETECT COLUMNS

    # -------------------------

    amount_col = next((c for c in df.columns if "amount" in c.lower()), None)

    date_col = next((c for c in df.columns if "date" in c.lower()), None)

    employee_col = next(

        (c for c in df.columns if "employee" in c.lower() and "code" in c.lower()),

        None

    )



    if not all([amount_col, date_col, employee_col]):

        return {

            "status": "FAILED",

            "reason": "MISSING_REQUIRED_COLUMNS",

            "columns_found": list(df.columns)

        }



    # -------------------------

    # 4. DATA CLEANING

    # -------------------------

    df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)



    # -------------------------

    # 5. TOTAL FILE LIMIT CHECK (FIX 🔥)

    # -------------------------

    file_total = df[amount_col].sum()



    if file_total > float(daily_limit):

        return {

            "status": "FAILED",

            "reason": "TOTAL_LIMIT_EXCEEDED",

            "daily_limit": float(daily_limit),

            "total_amount": float(file_total)

        }



    # -------------------------

    # 6. LOAD DATABASE

    # -------------------------

    if os.path.exists(EXCEL_DB):

        db_df = pd.read_excel(EXCEL_DB)

        db_df.columns = [str(c).strip() for c in db_df.columns]

    else:

        db_df = pd.DataFrame()



    # -------------------------

    # 7. DUPLICATE CHECK

    # -------------------------

    if not db_df.empty:
        db_amount_col = next((c for c in db_df.columns if "amount" in c.lower()), None)
        db_date_col = next((c for c in db_df.columns if "date" in c.lower()), None)
        db_employee_col = next(
            (c for c in db_df.columns if "employee" in c.lower() and "code" in c.lower()),
            None
        )

        db_df[db_date_col] = pd.to_datetime(db_df[db_date_col], errors="coerce", dayfirst=True)
        db_df[db_amount_col] = pd.to_numeric(db_df[db_amount_col], errors="coerce").fillna(0)

        duplicates = df.merge(
            db_df[[db_employee_col, db_date_col, db_amount_col]],
            left_on=[employee_col, date_col, amount_col],
            right_on=[db_employee_col, db_date_col, db_amount_col],
            how="inner"
        )



        if not duplicates.empty:

            return {

                "status": "FAILED",

                "reason": "ALREADY_CLAIMED_FOUND",

                "duplicate_records": int(len(duplicates)),
		"total_amount" : float(file_total),
		"total_records": len(df)
            }

    # -------------------------

    # 8. FINAL INSERT (ALL OR NOTHING)
    # -------------------------
    df["UploadedBy"] = uploaded_by
    df["Claim Type"] = "Daily Expense"

    final_df = pd.concat([db_df, df], ignore_index=True) if not db_df.empty else df
    final_df.to_excel(EXCEL_DB, index=False)



    # -------------------------

    # 9. SUCCESS

    # -------------------------

    return {
        "status": "SUCCESS",
        "total_records": int(len(df)),
        "total_amount": float(file_total)
    }

