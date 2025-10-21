FROM linkchat-base

WORKDIR /app
COPY app/ ./app/
COPY main.py ./

ENTRYPOINT [ "python", "main.py" ]

RUN pip install --no-cache-dir PyQt6