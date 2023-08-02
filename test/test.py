import sys
import boto3

command = sys.argv[1] if len(sys.argv) > 1 else "verify"

endpoint_url = "http://localstack-compere:4566"

sqs = boto3.client("sqs", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)

if command == "setup":
    print("Setting up AWS resources...")

    sqs.create_queue(QueueName="TestQueue")

    table = dynamodb.create_table(
        TableName="TestTable",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "N"}],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    )
    table.wait_until_exists()
    table.put_item(Item={"id": 123, "foo": "bar"})
elif command == "verify":
    print("Checking AWS resources still exist...")

    sqs.get_queue_url(QueueName="TestQueue")

    table = dynamodb.Table("TestTable")
    table.load()
    item = table.get_item(Key={"id": 123})["Item"]
    assert item["foo"] == "bar"
else:
    raise Exception("Unknown command: " + command)
