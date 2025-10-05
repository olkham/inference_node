# Use Python 3.11 slim as base image for better performance and smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV and other packages
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    wget \
    git \
    portaudio19-dev \
    libasound2-dev \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create necessary directories
RUN mkdir -p /app/InferenceNode/model_repository \
             /app/InferenceNode/logs \
             /app/InferenceNode/static \
             /app/InferenceNode/templates

# Set permissions for the application directory
RUN chmod -R 755 /app

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash infernode && \
    chown -R infernode:infernode /app
USER infernode

# Expose the default ports
EXPOSE 5555 8888/udp

# Set default port (can be overridden in docker-compose)
ENV NODE_PORT=5555

# Health check - uses NODE_PORT environment variable
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"NODE_PORT\", \"5555\")}/health', timeout=5)" || exit 1

# Default command to run the inference node in production mode
# Using shell form to allow environment variable expansion
CMD python main.py --port ${NODE_PORT} --production
