FROM python

RUN pip3 install boto3==1.28.80 botocore==1.31.80

COPY . .

ENTRYPOINT [ "python", "./test.py" ]