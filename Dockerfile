FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies required by several Python packages (onnxruntime, unstructured, libmagic, poppler)
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
		pkg-config \
		git \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip and install wheels first to ensure binary wheels are used where available
RUN pip install --upgrade pip setuptools wheel && \
		pip install --no-cache-dir -r requirements.txt

COPY src/ ./src

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
