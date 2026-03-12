import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("claimed_invoice")

response = table.put_item(
    Item={
        "File_Hash": "U1003",        # Partition Key
        "Claim_Type": "Test233", 
        "Claim_by": "Siddhant Kumar",
        "File_Name": "test1.pdf",
        "Invoice_Date": "15-dec-2026",
	"Invoice_Number": "INV-5433354",
	"String_Extracted":"test",
	"Total_Amount" : "3432",
	"Vendor" : "Uber"
    }
)

print(f"Item inserted successfully {response}")

