# Telegram Storage Bot

A Telegram bot that saves files to disk, with support for large files via local Bot API server.

## Project Structure

```
├── config.yaml          # Configuration file
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
│   │   └── access.py    # Access & throttle middleware
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py # File compression utilities
│       └── variables.py  # Paths and config
└── downloads/           # Saved files (created automatically)
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a bot with @BotFather and get the token

3. Configure `config.yaml` with your bot token and admin IDs

4. For large files (>20MB), set up the [local Bot API server](https://github.com/tdlib/telegram-bot-api):
```bash
./telegram-bot-api --api-id YOUR_API_ID --api-hash YOUR_API_HASH --token YOUR_BOT_TOKEN
```

5. Run the bot:
```bash
python -m src
```

## Configuration

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

## Commands

### Admin Commands
- `/add_user <telegram_id> [prefix]` - Add user to allowed list
- `/remove_user <telegram_id>` - Remove user from allowed list
- `/list_users` - List all users

### User Commands
- `/start` - Show greeting with current prefix
- `/set_prefix <prefix>` - Set file prefix (max 5 latin chars)

### Usage
- Send any file (document, photo, video, audio, voice, animation) - saved as gzip with prefix
- Send Docker image links - saved to docker_images.txt