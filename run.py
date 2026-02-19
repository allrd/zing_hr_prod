import pdfplumber

pdf = pdfplumber.open("bills_folder/invoice-4059842024232149839.pdf")
for i, page in enumerate(pdf.pages):
    print("\n===== PAGE", i+1, "=====\n")
    print(page.extract_text())
    # for dta in page:
    #     print(dta) 

