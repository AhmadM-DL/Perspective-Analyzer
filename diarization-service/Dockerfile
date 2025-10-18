FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch first (separate layer to avoid reinstalling on requirements changes)
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0

# Copy requirements
COPY requirements.txt .

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directory for diarization models
RUN mkdir -p /models/diarization

# Create directory for output files
RUN mkdir -p /app/outputs

# Expose port
EXPOSE 5002

# Run the application
CMD ["python", "app.py"]
