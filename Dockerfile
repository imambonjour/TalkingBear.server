FROM python:3.11-slim

# Install ffmpeg untuk pengolahan audio (Pydub)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode
COPY . .

# Jalankan server (port 8000 di dalam container)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
