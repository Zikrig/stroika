# Stroika Bot

Telegram bot for request lifecycle tracking in construction workflow.

## Stack
- Python 3.11+
- aiogram 3
- SQLite
- openpyxl
- Docker / docker-compose

## Quick start
1. Copy `.env.example` to `.env` and fill `BOT_TOKEN`.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Run bot:
   - `python -m app.main`

## Docker
- `docker compose up --build -d`

## Tests
- `pytest`
