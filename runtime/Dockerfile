FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY runtime-app.py ./
COPY .env ./

CMD ["python", "/app/runtime-app.py"]
