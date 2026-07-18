FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN apk add --no-cache chromium ca-certificates \
    && npm install --omit=dev \
    && npm cache clean --force
COPY server.js ./

RUN adduser -D -h /app pwuser \
    && mkdir -p /snapshots \
    && chown -R pwuser:pwuser /app

EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"
CMD ["sh", "-c", "chmod 0777 /snapshots && exec su -s /bin/sh pwuser -c 'exec node server.js'"]
