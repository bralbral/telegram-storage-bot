# Telegram Storage Bot

Telegram bot for saving files and Docker images to disk with gzip compression.

## Project Structure

```
├── .env.example          # Environment variables example
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker image
├── src/
│   ├── __main__.py      # Entry point
│   ├── handlers/        # Command handlers
│   ├── db/              # SQLite database
│   ├── middlewares/     # Access control & rate limiting
│   └── utils/           # File utilities
└── downloads/           # Saved files
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

```bash
docker build -t storage-bot .
docker run -d \
  --privileged \
  -e BOT_TOKEN="YOUR_TOKEN" \
  -e ADMIN_IDS="123456789" \
  -v $(pwd)/downloads:/var/lib/downloads \
  storage-bot
```

**Note**: Docker-in-Docker requires `--privileged` flag. The Docker daemon runs inside the container, and images are automatically deleted after export to save space.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Bot token from @BotFather |
| `ADMIN_IDS` | Yes | - | Comma-separated admin Telegram IDs |
| `DOWNLOAD_DIR` | No | ./downloads | Directory for downloaded files |
| `USE_LOCAL_API` | No | false | Enable local Bot API for large files |
| `LOCAL_API_URL` | No | http://127.0.0.1:8081 | Local Bot API server URL |

## Access Control

- **Admins**: Full access, auto-added to database, can use all commands
- **Regular users**: Must be added by admin, need prefix for files

## Usage

- **Send files** → saved as gzip with original filename preserved inside
- **Send `docker pull <image>`** → downloads and saves Docker image as gz
- **Send Docker links** → saved to docker_images.txt

## Commands

### Admin (visible only to admins)
- `/add_user <id> [prefix]` - Add user
- `/remove_user <id>` - Remove user
- `/list_users` - List all users
- `/status` - Bot status

### User (visible to everyone)
- `/start` - Show greeting
- `/set_prefix <prefix>` - Set file prefix (1-5 chars)
