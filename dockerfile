FROM python:3.13-slim

# For security functions
RUN pip install cryptography

WORKDIR /app
COPY app/ ./app/
COPY main.py ./

ENTRYPOINT [ "python", "main.py" ]
