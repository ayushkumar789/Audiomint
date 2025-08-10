# ---- Base
FROM python:3.11-slim

# System deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Python deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1 \
    PORT=10000 \
    HOST=0.0.0.0

# Start with gunicorn
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:10000", "app.wsgi:app", "--threads", "8", "--timeout", "180"]
