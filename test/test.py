import sys
import boto3


def assert_equal(a, b):
    assert a == b, "%s != %s" % (a, b)


command = sys.argv[1] if len(sys.argv) > 1 else "verify"

endpoint_url = "http://localstack-compere:4566"

sqs = boto3.resource("sqs", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
s3 = boto3.resource("s3", endpoint_url=endpoint_url)

if command == "setup":
    print("Setting up AWS resources...")

    sqs.create_queue(QueueName="test-queue", Attributes={"DelaySeconds": "123"})

    table = dynamodb.create_table(
        TableName="test-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "N"}],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    )
    table.wait_until_exists()
    table.put_item(Item={"id": 123, "foo": "bar"})

    bucket = s3.create_bucket(Bucket="test-bucket")
    bucket.put_object(Key="test-object", Body=b"object data")
elif command == "verify":
    print("Checking AWS resources still exist...")

    queue = sqs.Queue("test-queue")
    queue.load()
    assert_equal(queue.attributes["DelaySeconds"], "123")

    table = dynamodb.Table("test-table")
    item = table.get_item(Key={"id": 123})["Item"]
    assert_equal(item["foo"], "bar")

    bucket = s3.Bucket("test-bucket")
    obj = bucket.Object("test-object")
    body = obj.get()["Body"].read()
    assert_equal(body, b"object data")
else:
    raise Exception("Unknown command: " + command)
