import sys
import boto3

command = sys.argv[1] if len(sys.argv) > 1 else "verify"

endpoint_url = "http://localstack-compere:4566"

sqs = boto3.client("sqs", endpoint_url=endpoint_url)

if command == "setup":
    print("Setting up AWS resources...")
    sqs.create_queue(QueueName="SQS_QUEUE_NAME")
elif command == "verify":
    print("Checking AWS resources still exist...")
    sqs.get_queue_url(QueueName="SQS_QUEUE_NAME")
else:
    raise Exception("Unknown command: " + command)
