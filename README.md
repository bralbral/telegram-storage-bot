# Telegram Storage Bot

A Telegram bot that saves files to disk, with support for large files via local Bot API server.

## Project Structure

```
├── config.example.yaml  # Example configuration file
├── config.yaml          # Configuration file (not in git)
├── requirements.txt     # Python dependencies
├── src/
│   ├── __main__.py      # Entry point
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── admin.py     # Admin commands
│   │   ├── docker.py    # Docker link handling
│   │   ├── files.py     # File handling
│   │   └── user.py      # User commands
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py  # SQLite database with aiosqlite
│   ├── middlewares/
│   │   ├── access.py    # Access & throttle middleware
│   │   └── throttle.py  # Rate limiting middleware
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py # File compression utilities
│       └── variables.py  # Paths and config
└── downloads/           # Saved files (created automatically)
```

## Setup

### Local Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a bot with @BotFather and get the token

3. Copy the example configuration and edit it:
```bash
cp config.example.yaml config.yaml
```

4. Configure `config.yaml` with your bot token and admin IDs

5. For large files (>20MB), set up the [local Bot API server](https://github.com/tdlib/telegram-bot-api):
```bash
./telegram-bot-api --api-id YOUR_API_ID --api-hash YOUR_API_HASH --token YOUR_BOT_TOKEN
```

6. Run the bot:
```bash
python -m src
```

### Docker Setup

1. Build the Docker image:
```bash
docker build -t storage-bot .
```

2. Run the container with environment variables:
```bash
docker run -d \
  -e BOT_TOKEN="YOUR_BOT_TOKEN" \
  -e ADMIN_IDS="123456789,987654321" \
  -e USE_LOCAL_API="false" \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/users.db:/app/users.db \
  storage-bot
```

## Configuration

### Using config.yaml

```yaml
bot:
  token: YOUR_BOT_TOKEN
  use_local_api: true              # Enable local Bot API for large files
  local_api_url: http://127.0.0.1:8081
  admin_ids:                       # Telegram IDs of admins
    - 123456789

storage:
  download_dir: ./downloads
```

### Using Environment Variables

- `BOT_TOKEN` - Your bot token (required)
- `USE_LOCAL_API` - Set to "true" to use local Bot API (default: false)
- `LOCAL_API_URL` - Local Bot API server URL (default: http://127.0.0.1:8081)
- `ADMIN_IDS` - Comma-separated list of admin Telegram IDs (optional)

## Features

- **File Storage**: Compress and save files as gzip with user-defined prefixes
- **Docker Links**: Save Docker image links to a text file
- **Access Control**: Admin-managed user access list
- **Rate Limiting**: Built-in throttling to prevent abuse
- **Large File Support**: Optional local Bot API server for files >20MB
- **Logging**: Comprehensive logging for monitoring and debugging
- **Docker Support**: Containerized deployment with environment variable configuration

## Commands

### Admin Commands
- `/add_user <telegram_id> [prefix]` - Add user to allowed list with optional prefix
- `/remove_user <telegram_id>` - Remove user from allowed list
- `/list_users` - List all users with their prefixes

### User Commands
- `/start` - Show greeting with current prefix
- `/set_prefix <prefix>` - Set file prefix (1-5 latin alphanumeric characters)

### Usage
- Send any file (document, photo, video, audio, voice, animation) - saved as gzip with prefix
- Send Docker image links - saved to docker_images.txt

## Security Improvements

- SHA256 hashing for file integrity (replacing MD5)
- Input validation for all user inputs
- Enhanced error handling and logging
- Admin command authorization checking
- Config validation and error reporting

## Development

### Code Quality Tools

The project uses pre-commit hooks for code quality:
- Ruff for linting and formatting
- MyPy for type checking
- isort for import sorting

Install pre-commit hooks:
```bash
pre-commit install
```

Run checks manually:
```bash
pre-commit run --all-files
```
