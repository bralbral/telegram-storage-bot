# Official Docker-in-Docker image
FROM docker:dind

# Install Python and pip in Alpine
RUN apk add --no-cache python3 py3-pip

# Create virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create download directory
RUN mkdir -p /var/lib/downloads

# Environment variables
ENV DOCKER_HOST=unix:///var/run/docker.sock
ENV PYTHONUNBUFFERED=1

# Start Docker daemon using official entrypoint, then run the bot
# dockerd-entrypoint.sh already sets up Docker daemon correctly
# dockerd logs redirected to file to keep only application logs in docker logs
CMD ["dockerd-entrypoint.sh", "sh", "-c", "dockerd >/var/log/dockerd.log 2>&1 & sleep 5 && python -m src"]
