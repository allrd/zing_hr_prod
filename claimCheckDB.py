import boto3
from decimal import Decimal

dynamodb = boto3.resource(
	"dynamodb",
	region_name="ap-south-1"
)

table = dynamodb.Table("CLAIM-DATA")
print(table)

item = {
	"Claim_ID":"Test123232",
	"Invoice_No":"TestInvoice",
	"Employee_Code":"ss",
	"Date":"1 Jan",
	"Claim_Type":"Approved",
	"Status":"Reject",
	"Total_Amount":"1232",
	"HASH":"Test"
}

table.put_item(Item=item)
