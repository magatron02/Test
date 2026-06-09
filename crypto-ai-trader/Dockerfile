FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TRADER_BASE_DIR=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8888

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8888"]
