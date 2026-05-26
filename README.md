# Telegram Storage Bot

Telegram bot for saving files and Docker images to disk with gzip compression. Features Docker-in-Docker support with structured logging and health monitoring.

## Project Structure

```
├── .env.example          # Environment variables example
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker Compose configuration
├── src/
│   ├── __main__.py      # Entry point
│   ├── logging_config.py # Structured logging configuration
│   ├── handlers/        # Command handlers
│   ├── db/              # SQLite database
│   ├── middlewares/     # Access control & rate limiting
│   ├── health.py        # Health check server
│   └── utils/           # File utilities
├── downloads/           # Saved files
└── telegram-api-data/   # Telegram Bot API data files
```

## Quick Start

### Local

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your values
```

3. Run:
```bash
python -m src
```

### Docker

#### Using Docker Compose (Recommended)

```bash
cp .env.example .env
# Edit .env with your values:
# - BOT_TOKEN from @BotFather
# - ADMIN_IDS (your Telegram ID)
# - TELEGRAM_API_ID and TELEGRAM_API_HASH from https://my.telegram.org (for local Bot API)
docker compose up -d
```

The bot includes a local Telegram Bot API server for downloading files larger than 20MB. Get your API credentials from https://my.telegram.org.

#### Using Docker CLI

```bash
docker build -t storage-bot .
docker run -d \
  --privileged \
  -e BOT_TOKEN="YOUR_TOKEN" \
  -e ADMIN_IDS="123456789" \
  -v $(pwd)/downloads:/var/lib/downloads \
  storage-bot
```

**Note**: Docker-in-Docker requires `--privileged` flag. The bot uses the official `docker:dind` image for reliable Docker-in-Docker support. Images are automatically deleted after export to save space.

### Health Check

The bot includes a health check endpoint for monitoring:
```bash
curl http://localhost:8080/health
```

Returns JSON with bot and Docker daemon status. Docker Compose includes automatic health checks.

### Logs

The bot uses structured logging with readable console output:
```bash
docker logs storage-bot -f
```

- Application logs are clean and readable (no aiogram/aiohttp noise)
- Docker daemon logs are redirected to `/var/log/dockerd.log` inside container
- Log level can be controlled via `LOG_LEVEL` environment variable

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Bot token from @BotFather |
| `ADMIN_IDS` | Yes | - | Comma-separated admin Telegram IDs |
| `DOWNLOAD_DIR` | No | ./downloads | Directory for downloaded files |
| `DB_PATH` | No | ./users.db | Database file path |
| `MAX_FILE_SIZE` | No | 2147483648 (2GB) | Maximum file size in bytes |
| `THROTTLE_RATE` | No | 3.0 | Throttle rate in seconds |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `HEALTH_PORT` | No | 8080 | Health check server port |
| `DOCKER_HOST` | No | unix:///var/run/docker.sock | Docker daemon socket URL |
| `TELEGRAM_API_ID` | Yes (for local API) | - | Telegram API ID from https://my.telegram.org |
| `TELEGRAM_API_HASH` | Yes (for local API) | - | Telegram API Hash from https://my.telegram.org |
| `USE_LOCAL_API` | No | true | Enable local Bot API for large files (>20MB) |
| `LOCAL_API_URL` | No | http://telegram-bot-api:8081 | Local Bot API server URL (internal Docker network) |

## Local Telegram Bot API

The bot includes a local Telegram Bot API server for downloading files larger than 20MB. The local API server runs in a separate container and is automatically configured in Docker Compose.

### Setup

1. Get API credentials from https://my.telegram.org
2. Add `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` to your `.env` file
3. Set `USE_LOCAL_API=true` (default)
4. Start with Docker Compose

### Access

- **Internal Docker network**: `http://telegram-bot-api:8081` (used by storage-bot)
- **Data directory**: `./telegram-api-data` (on host machine, accessible for backup/inspection)

The local API server provides:
- Support for files up to 2GB
- Better performance for large files
- Reduced dependency on Telegram's servers
- Data persistence via host volume mapping

## Access Control

- **Admins**: Full access, auto-added to database, can use all commands
- **Regular users**: Must be added by admin, need prefix for files

## Usage

- **Send files** → saved as gzip with original filename preserved inside (max 2GB)
  - Already compressed files (.gz, .zip, .rar, .7z, .tar, etc.) saved without additional compression
  - Files are named with user prefix if set (e.g., `user_prefix_filename.tar.gz`)
- **Send `docker pull <image>`** → downloads and saves Docker image as gz
  - Docker image is automatically removed after export to save space

## Commands

### Admin (visible only to admins)
- `/add_user <id> [prefix]` - Add user (prefix is optional, 1-10 latin alphanumeric chars if provided)
- `/remove_user <id>` - Remove user
- `/list_users` - List all users
- `/status` - Bot status and system information

### User (visible to everyone)
- `/start` - Show greeting
- `/my_prefix` - Show your current prefix
- `/set_prefix <prefix>` - Set file prefix (1-10 latin alphanumeric characters)
