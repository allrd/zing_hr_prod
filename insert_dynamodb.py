import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("claimed_invoice")

response = table.put_item(
    Item={
        "File_Hash": "U1002",        # Partition Key
        "Claim_Type": "Test23", 
        "Claim_by": "Manish mar",
        "File_Name": "test.pdf",
        "Invoice_Date": "15-dec-2026",
	"Invoice_Number": "INV-544354",
	"String_Extracted":"test",
	"Total_Amount" : "4322",
	"Vendor" : "Ola"
    }
)

print(f"Item inserted successfully {response}")

