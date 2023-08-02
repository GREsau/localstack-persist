FROM python

RUN pip3 install boto3

COPY . .

ENTRYPOINT [ "python", "./test.py" ]