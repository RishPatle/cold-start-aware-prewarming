FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Knative will inject PORT=8080 by default
EXPOSE 8080

# Use gunicorn (production-grade) with 1 worker for predictable cold-start measurements
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "app:app"]