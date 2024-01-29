FROM umihico/aws-lambda-selenium-python:3.12.0
RUN pip install requests==2.31.0

COPY main.py ./
CMD [ "main.handler" ]