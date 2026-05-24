FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p downloads

ENV BOT_TOKEN=""
ENV USE_LOCAL_API="false"
ENV LOCAL_API_URL="http://127.0.0.1:8081"
ENV ADMIN_IDS=""

CMD ["python", "-m", "src"]
