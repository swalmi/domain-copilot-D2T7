FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Minimal system deps for the API runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.base.txt .

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.base.txt

COPY src/ ./src

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
