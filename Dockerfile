FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directories for data and logs
RUN mkdir -p data logs && chmod 755 data logs

# Set environment
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "bot.py"]
