FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Ensure Python can import the `src` package path
ENV PYTHONPATH=/app

# System deps for the API runtime plus document parsing (unstructured, onnxruntime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libgomp1 \
    libmagic1 \
    poppler-utils \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    pkg-config \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.base.txt requirements.worker.txt ./

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.base.txt && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir -r requirements.worker.txt && \
    pip install --no-cache-dir --no-deps langchain-unstructured==0.1.6

COPY alembic.ini .
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY src/ ./src
COPY prompts/ ./prompts

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
