import sys
from time import sleep
import boto3
import io
import zipfile
import urllib.request
import json


def assert_equal(a, b):
    assert a == b, "%s != %s" % (a, b)


def wait_until_es_ready(domain_name: str):
    for _ in range(180):
        es_domain = elasticsearch.describe_elasticsearch_domain(DomainName=domain_name)
        if not es_domain["DomainStatus"].get("Processing", True):
            sleep(1)
            return es_domain
        sleep(1)
    raise Exception(f"ElasticSearch domain {domain_name} was not ready after 180s")


command = sys.argv[1] if len(sys.argv) > 1 else "verify"

endpoint_url = "http://localstack-persist:4566"

sqs = boto3.resource("sqs", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
s3 = boto3.resource("s3", endpoint_url=endpoint_url)
iam = boto3.resource("iam", endpoint_url=endpoint_url)
lambda_client = boto3.client("lambda", endpoint_url=endpoint_url)
acm = boto3.client("acm", endpoint_url=endpoint_url)
elasticsearch = boto3.client("es", endpoint_url=endpoint_url)

cert = open("cert.pem", "r").read()
cert_key = open("key.pem", "r").read()

if command == "setup":
    print("Setting up AWS resources...")

    elasticsearch.create_elasticsearch_domain(
        ElasticsearchVersion="7.10",
        DomainName="test-es-domain",
        DomainEndpointOptions={
            "CustomEndpoint": endpoint_url + "/test-es-domain-endpoint",
            "CustomEndpointEnabled": True,
        },
    )

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

    zipbuf = io.BytesIO()
    with zipfile.ZipFile(zipbuf, "w") as zip:
        zip.write("lambda/bootstrap", "bootstrap")
    lambda_client.create_function(
        FunctionName="test-lambda",
        Role=role.arn,
        Code={"ZipFile": zipbuf.getvalue()},
        Runtime="provided",
    )

    acm.import_certificate(Certificate=cert, PrivateKey=cert_key)

    wait_until_es_ready("test-es-domain")
    put_index_req = urllib.request.Request(
        endpoint_url + "/test-es-domain-endpoint/test-es-index", method="PUT"
    )
    with urllib.request.urlopen(put_index_req) as res:
        pass

elif command == "verify":
    print("Checking AWS resources still exist...")

    queue = sqs.Queue("test-queue")
    assert_equal(queue.attributes["DelaySeconds"], "123")
    assert_equal(queue.attributes["ApproximateNumberOfMessages"], "0")

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
    with urllib.request.urlopen(lambda_code_location) as res:
        with zipfile.ZipFile(io.BytesIO(res.read())) as zip:
            assert_equal(zip.read("bootstrap"), open("lambda/bootstrap", "rb").read())
    lambda_client.get_waiter("function_active_v2").wait(FunctionName="test-lambda")
    lambda_response = lambda_client.invoke(
        FunctionName="test-lambda", Payload="hello world"
    )
    assert_equal(lambda_response["ResponseMetadata"]["HTTPStatusCode"], 200)
    assert_equal(lambda_response["Payload"].read(), b"HELLO WORLD")

    certs = acm.list_certificates()
    assert_equal(certs["CertificateSummaryList"][0].get("DomainName", None), "test")

    wait_until_es_ready("test-es-domain")
    es_index_url = endpoint_url + "/test-es-domain-endpoint/test-es-index"
    with urllib.request.urlopen(es_index_url) as res:
        es_index = json.loads(res.read().decode("utf-8"))
    num_shards = es_index["test-es-index"]["settings"]["index"]["number_of_shards"]
    assert_equal(str(num_shards), "1")


else:
    raise Exception("Unknown command: " + command)
