FROM python:3.12-slim

# Install Docker
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-ce docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /var/lib/downloads

# Environment variables
ENV BOT_TOKEN=""
ENV ADMIN_IDS=""
ENV USE_LOCAL_API="false"
ENV LOCAL_API_URL="http://127.0.0.1:8081"
ENV DOWNLOAD_DIR="/var/lib/downloads"

# Docker daemon configuration
ENV DOCKER_TLS_CERTDIR=""
ENV DOCKER_HOST=unix:///var/run/docker.sock

# Start script
CMD set -e; \
    echo "Starting..."; \
    which python; \
    python --version; \
    ls -la /app/src/; \
    echo "Starting Docker daemon..."; \
    dockerd > /tmp/dockerd.log 2>&1 & \
    DOCKERD_PID=$!; \
    echo "Waiting for Docker daemon to be ready (PID: $DOCKERD_PID)..."; \
    for i in $(seq 1 30); do \
        if docker info > /dev/null 2>&1; then \
            echo "Docker daemon is ready"; \
            break; \
        fi; \
        echo "Attempt $i: Docker daemon not ready yet"; \
        sleep 1; \
    done; \
    if ! docker info > /dev/null 2>&1; then \
        echo "Docker daemon failed to start"; \
        cat /tmp/dockerd.log; \
        exit 1; \
    fi; \
    echo "Starting bot..."; \
    python -m src
