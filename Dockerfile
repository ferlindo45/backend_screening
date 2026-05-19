# Stage 1: Build dependencies
FROM python:3.10-slim as builder

WORKDIR /app

# Install build essentials for packages like xgboost or psutil
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final image
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY . .

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Create logs directory
RUN mkdir -p logs

EXPOSE 8000

# Run the application
CMD ["python", "run.py"]
