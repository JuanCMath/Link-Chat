FROM python:3.13-slim

WORKDIR /app
COPY app/ ./app/
COPY main.py ./

# For security functions
RUN pip install --no-cache-dir cryptography

ENTRYPOINT [ "python", "main.py" ]
