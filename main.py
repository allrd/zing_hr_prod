import os
import tempfile

# import the updated safe decryption functions
from dec import safe_decrypt_text as decrypt_text
from dec import safe_decrypt_file as decrypt_file

from date import extract_date_from_text
from total import extract_total
from invoice import extract_invoice
from ven1 import get_vendor
from total import extract_text_full


# -------------------------------------------------------------
# MAIN FUNCTION
# -------------------------------------------------------------
def process_invoice_request(enc_date, enc_total, enc_invoice, enc_vendor, enc_file):

    # STEP 1 — decrypt all text fields safely
    dec_expected_date = decrypt_text(enc_date)
    dec_expected_total = decrypt_text(enc_total)
    dec_expected_invoice = decrypt_text(enc_invoice)
    dec_expected_vendor = decrypt_text(enc_vendor)

    # STEP 2 — decrypt actual uploaded file (Base64 → bytes)
    file_bytes = decrypt_file(enc_file)

    # STEP 3 — save decrypted file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    # STEP 4 — extract text from the invoice
    text = extract_text_full(temp_path)

    found_date = extract_date_from_text(text)
    found_total = extract_total(text)
    found_invoice = extract_invoice(text)
    found_vendor = get_vendor(temp_path)

    # STEP 5 — compare extracted values with expected values
    result = {
        "date": found_date,
        "date_match": (found_date == dec_expected_date),

        "total": found_total,
        "total_match": (str(found_total).replace(" ", "") ==
                        dec_expected_total.replace(" ", "")),

        "invoice": found_invoice,
        "invoice_match": (found_invoice.lower() ==
                          dec_expected_invoice.lower()),

        "vendor": found_vendor,
        "vendor_match": (found_vendor.lower() ==
                         dec_expected_vendor.lower()),
    }

    # remove temporary decrypted file
    os.remove(temp_path)

    return result


# -------------------------------------------------------------
# TEST
# -------------------------------------------------------------
if __name__ == "__main__":
    print("Main ready — waiting for encrypted inputs")
