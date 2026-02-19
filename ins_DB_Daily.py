import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("daily-expenses")

response = table.put_item(
    Item={
        "ID": "1002",        # Partition Key
        "Claim_Type": "Test23",
        "Description": "Manish mar",
        "emp_code": "E-2323",
        "Invoice Date": "15-dec-2026",
        "Total_Amount": "232",
        "Uploaded_By":"mahesh"
    }
)

print(f"Item inserted successfully {response}")
