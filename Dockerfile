FROM docker:dind

# Install Python
RUN apk add --no-cache python3 py3-pip

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

# Docker daemon configuration for DinD
ENV DOCKER_TLS_CERTDIR=""
ENV DOCKER_HOST=unix:///var/run/docker.sock

# Create startup script
RUN echo '#!/bin/sh\n\
# Start Docker daemon in background\n\
dockerd-entrypoint.sh &\n\
# Wait for Docker daemon to be ready\n\
while ! docker info > /dev/null 2>&1; do\n\
  echo "Waiting for Docker daemon to start..."\n\
  sleep 1\n\
done\n\
echo "Docker daemon is ready"\n\
# Run the bot\n\
python -m src' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
