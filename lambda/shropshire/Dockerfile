FROM public.ecr.aws/lambda/python:3.12

# Install dependencies
RUN pip install playwright boto3 botocore -t ${LAMBDA_TASK_ROOT}

# Install playwright browsers (chromium only, headless)
RUN python -m playwright install chromium

# Copy function code
COPY main.py ${LAMBDA_TASK_ROOT}

CMD ["main.handler"]
