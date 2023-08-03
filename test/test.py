import sys
import boto3
import io
import zipfile
import urllib.request


def assert_equal(a, b):
    assert a == b, "%s != %s" % (a, b)


command = sys.argv[1] if len(sys.argv) > 1 else "verify"

endpoint_url = "http://localstack-persist:4566"

sqs = boto3.resource("sqs", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
s3 = boto3.resource("s3", endpoint_url=endpoint_url)
iam = boto3.resource("iam", endpoint_url=endpoint_url)
lambda_client = boto3.client("lambda", endpoint_url=endpoint_url)
acm = boto3.client("acm", endpoint_url=endpoint_url)

zipbuf = io.BytesIO()
zipfile.ZipFile(zipbuf, "w").close()

cert = open("cert.pem", "r").read()
cert_key = open("key.pem", "r").read()

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

    role = iam.create_role(RoleName="test-role", AssumeRolePolicyDocument="{}")

    lambda_client.create_function(
        FunctionName="test-lambda",
        Role=role.arn,
        Code={"ZipFile": zipbuf.getvalue()},
        Runtime="provided",
    )

    acm.import_certificate(Certificate=cert, PrivateKey=cert_key)

elif command == "verify":
    print("Checking AWS resources still exist...")

    queue = sqs.Queue("test-queue")
    assert_equal(queue.attributes["DelaySeconds"], "123")

    table = dynamodb.Table("test-table")
    item = table.get_item(Key={"id": 123})["Item"]
    assert_equal(item["foo"], "bar")

    bucket = s3.Bucket("test-bucket")
    obj = bucket.Object("test-object")
    body = obj.get()["Body"].read()
    assert_equal(body, b"object data")

    role = iam.Role("test-role")

    lambda_response = lambda_client.get_function(FunctionName="test-lambda")
    assert_equal(lambda_response["Configuration"].get("Role", None), role.arn)
    lambda_code_location = lambda_response["Code"].get("Location", "")
    with urllib.request.urlopen(lambda_code_location) as f:
        assert_equal(f.read(), zipbuf.getvalue())

    certs = acm.list_certificates()
    assert_equal(certs["CertificateSummaryList"][0].get("DomainName", None), "test")

else:
    raise Exception("Unknown command: " + command)
