# Koristi Python 3.9 za Mac M1/M2 (ARM64)
FROM --platform=linux/arm64 python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]



