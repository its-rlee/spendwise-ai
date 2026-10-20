
# Use the official Python 3.15 Linux image
FROM python:3.15-slim-bookworm

# Python settings suitable for containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Working directory inside the container
WORKDIR /app

# Install the Linux Tesseract OCR executable
# and English language data
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements separately for build caching
COPY requirements.txt ./requirements.txt

# Install Python dependencies
RUN python -m pip install -r requirements.txt

# Copy only our application code
COPY app ./app

# Run the web application as a non-root user
RUN useradd --create-home --uid 10001 appuser

USER appuser

# Document the container's application port
EXPOSE 8000

# Start FastAPI
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
