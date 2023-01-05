FROM umihico/aws-lambda-selenium-python:latest
RUN pip install requests

COPY main.py ./
CMD [ "main.handler" ]