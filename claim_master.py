import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("CLAIM-DATA")

response = table.put_item(
    Item={
        "HASH": "U1003",        # Partition Key
        "Employee_Code": "Test233", 
        "Invoice_No": "Siddhant Kumar",
        "Date": "15-dec-2026",
        "Total_Amount" : "3432",
	"Claim_Type" : "Uber"
    }
)

print(f"Item inserted successfully {response}")

