# Telegram Storage Bot

Telegram bot that saves user files as `tar.gz` archives and exports Docker
images as `.tar.gz` files. It is designed to run with Docker-in-Docker (DIND)
and a local Telegram Bot API to handle files up to 2 GB.

## Quick start

### Docker Compose

```bash
cp .env.example .env
# Set BOT_TOKEN, ADMIN_IDS, TELEGRAM_API_ID, and TELEGRAM_API_HASH
docker compose up -d --build
```

After startup:

- completed archives and exported images are in `./downloads`;
- the user database and file queue are in `./data/users.db`;
- local Telegram Bot API data is in `./telegram-local-api`;
- the health endpoint is available at `http://localhost:8080/health`.

To use the local Telegram Bot API, obtain `TELEGRAM_API_ID` and
`TELEGRAM_API_HASH` from <https://my.telegram.org>.

### Local run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src
```

When running without containers, set `USE_LOCAL_API=false` in `.env` unless a
local Telegram Bot API is already running. The Docker daemon must be reachable
through `DOCKER_HOST`.

### Docker CLI

```bash
docker build -t storage-bot .
docker run -d --name storage-bot --privileged \
  -p 8080:8080 \
  -e BOT_TOKEN="YOUR_TOKEN" \
  -e ADMIN_IDS="123456789" \
  -e USE_LOCAL_API=false \
  -v "$(pwd)/downloads:/downloads" \
  -v "$(pwd)/data:/app/data" \
  storage-bot
```

`--privileged` is required for DIND and is intentionally retained in this
project's configuration.

## Access control

- Administrators listed in `ADMIN_IDS` are granted access automatically.
- An administrator must add a regular user with `/add_user`.
- Users must set a prefix with `/set_prefix` before sending files or requesting
  Docker images.
- New, unregistered users can only use `/start` and are throttled by
  `THROTTLE_RATE`.

## File workflow

1. Send files to the bot; they are added to your personal queue.
2. Review the queue with `/buffer`.
3. Run `/drop`; the bot downloads the queued files and creates one `tar.gz`
   archive in `DOWNLOAD_DIR`.

The queue is stored in SQLite, so it survives a container restart. A file is
removed from the queue only after it has been added to a completed archive. If
an individual file cannot be downloaded, it remains queued and the bot reports
the number of failures.

During `/drop`, the queue is reserved. A second `/drop`, `/clear`, and newly
sent files are rejected until archiving finishes. This prevents duplicate file
exports and race conditions.

By default, each user may queue up to 100 files with a total size of 10 GB.
Configure these limits with `MAX_BUFFER_FILES` and `MAX_BUFFER_SIZE`.

## Docker image workflow

Send a message in this form:

```text
docker pull nginx:latest
```

The bot removes a previous local copy of the image, pulls the requested image,
streams its export directly into a `.tar.gz` file, and removes the image from
DIND. No full temporary `.tar` file is created. Operations for the same image
do not overlap; `MAX_DOCKER_OPERATIONS` controls total concurrent pull/export
jobs (default: `1`).

## Commands

### All users

- `/start` — show a greeting and short instructions.
- `/my_prefix` — show the current prefix.
- `/set_prefix <prefix>` — set a prefix of 1–10 Latin letters, digits, or `_`.
- `/buffer` — show queued files and their total size.
- `/drop` — create an archive from the queue.
- `/clear` — clear the queue when archiving is not in progress.

### Administrators

- `/add_user <telegram_id> [prefix]` — add a user.
- `/remove_user <telegram_id>` — remove a user.
- `/list_users` — list users.
- `/status` — show the process status.

## Environment variables

| Variable | Default | Description |
|---|---:|---|
| `BOT_TOKEN` | — | Bot token from BotFather; required. |
| `ADMIN_IDS` | — | Comma-separated administrator Telegram IDs; required. |
| `DOWNLOAD_DIR` | `./downloads` | Directory for completed archives and images. In Compose: `/downloads`. |
| `DB_PATH` | `./users.db` | SQLite database path. In Compose: `/app/data/users.db`. |
| `MAX_FILE_SIZE` | `2147483648` | Maximum size of a single incoming file, in bytes. |
| `MAX_BUFFER_FILES` | `100` | Maximum queued files per user. |
| `MAX_BUFFER_SIZE` | `10737418240` | Maximum combined queue size per user, in bytes. |
| `MAX_DOCKER_OPERATIONS` | `1` | Maximum concurrent Docker pull/export jobs. |
| `THROTTLE_RATE` | `3.0` | Throttling interval for unregistered users, in seconds. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `HEALTH_PORT` | `8080` | Health endpoint port. |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon address. |
| `USE_LOCAL_API` | `true` | Whether to use the local Telegram Bot API. |
| `LOCAL_API_URL` | `http://127.0.0.1:8081` | Local Telegram Bot API URL. |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | — | Required by the local Telegram Bot API service. |

## Monitoring and tests

```bash
curl http://localhost:8080/health
python -m pytest -q tests
pre-commit run --all-files
```

`/health` reports the service state and Docker daemon availability. Docker is
checked outside the event loop with a short timeout, so an unresponsive daemon
does not block message handling. Tests are also included in the local hook in
`.pre-commit-config.yaml`.

Application logs include `user_id`, `chat_id`, and `message_id` for every
Telegram update, as well as an `action` such as `/drop`, `file_upload`, or
`docker_pull`. The same context is retained by background archive and Docker
tasks.
