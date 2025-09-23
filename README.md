## AI Moderation & Spam Detection

This bot includes profanity/toxicity detection (RU-friendly) and spam heuristics.

- AI backends:
  - Local rules (always available)
  - HuggingFace model: `cointegrated/rubert-tiny-toxicity`
  - Detoxify multilingual (optional)
  - Ensemble (max of available signals)

Environment variables (optional):
Hello
```
AI_BACKEND=ensemble
AI_PROFANITY_THRESHOLD=0.5
SPAM_SCORE_THRESHOLD=0.6
AI_DISABLE_HF=0
```

Install dependencies:

```
pip install -r requirements.txt
```
.\.venv312\Scripts\Activate.ps1
$Env:AI_DISABLE_HF='0'; $Env:AI_BACKEND='ensemble'; python bot.py

$Env:AI_PROFANITY_ENABLED='1'
$Env:AI_DISABLE_HF='0'
$Env:AI_BACKEND='ensemble'
$Env:AI_PROFANITY_THRESHOLD='0.7'

# ShadowX - Anonymous Student Messaging Bot

ShadowX is an anonymous messaging bot for university students, allowing them to send messages to university-specific channels while maintaining anonymity.

## Features

- **Multilingual Support**: Available in English and Russian
- **Anonymous Messaging**: Post messages to your university's channel without revealing your identity
- **Different Message Types**: Regular messages, help requests, and confessions
- **Media Support**: Send photos and videos (subject to moderation)
- **Smart Filtering**: 
  - Profanity filter that replaces banned words with asterisks
  - Suspicious content detection for ads and inappropriate material
  - All filtered content goes through human moderation
- **Anti-spam Queue**: Messages are queued and sent gradually to prevent flooding
- **University System**: Support for multiple universities with dedicated channels
- **Moderation System**: Admin approval for sensitive content

## Project Structure

```
ShadowX/
├── bot.py                 # Main entry point
├── config.py              # Configuration (tokens, IDs, settings)
├── database.py            # Database operations
├── handlers/              # Message and command handlers
│   ├── language.py        # Language selection and text localization
│   ├── media.py           # Media message handling
│   ├── messages.py        # Text message handling
│   └── moderation.py      # Admin moderation functions
└── utils/                 # Utility modules
    ├── filters.py         # Content filtering
    └── queue.py           # Message queue system
```

## Installation

1. Clone the repository
2. Python 3.11+ recommended
3. Install core deps:
   - `pip install aiogram`
4. Optional: Enable local AI moderation (recommended)
   - In `config.py` set `AI_PROFANITY_ENABLED = True` (already enabled by default)
   - Install inference deps (CPU-only):
     - `python -m pip install --upgrade pip`
     - `pip install torch --index-url https://download.pytorch.org/whl/cpu`
     - `pip install transformers detoxify langid`
5. Environment
   - Create `.env` next to `bot.py`:
     
     ```ini
     BOT_TOKEN=your_telegram_bot_token
     # Optional
     AI_PROFANITY_ENABLED=0
     AI_BACKEND=ensemble
     AI_PROFANITY_THRESHOLD=0.7
     SPAM_SCORE_THRESHOLD=0.6
     MIN_MESSAGE_WORDS=4
     # Safer queue spacing (seconds)
     MESSAGE_QUEUE_MIN_INTERVAL=20
     MESSAGE_QUEUE_MAX_INTERVAL=30
     # Admins (comma/space separated IDs)
     ADMIN_IDS=6336309736,5694951691
     # Optional: primary admin and usernames mapping
     # ADMIN_ID=6336309736
     # ADMIN_USERNAME=@owner_username
     # ADMIN_USERNAMES=6336309736:@owner_username,5694951691:@second_admin
     # Set DB path explicitly (default: ./bot_database.db)
     # DB_PATH=/data/bot_database.db
     ```
6. Run the bot: `python bot.py`

## Docker deployment

1. Build and run with persistent storage:

   ```bash
   docker compose up -d --build
   ```

2. Update `.env` (host) to set `BOT_TOKEN` and optional flags; container restarts will pick them up.

3. Data persistence:
   - SQLite file stored in named volume `shadowx_data` at `/data/bot_database.db` in the container.

4. Using HTTP(S) proxy (optional):
   - Uncomment proxy envs in `docker-compose.yml` and set credentials.

## Offline/Local model caching

- Models are downloaded once to your Hugging Face cache (`~/.cache/huggingface` on most systems).
- To prefetch the Russian toxicity model locally (optional):
  ```bash
  python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; m='cointegrated/rubert-tiny-toxicity'; AutoTokenizer.from_pretrained(m); AutoModelForSequenceClassification.from_pretrained(m)"
  ```
- After download, inference runs locally. Internet is only needed for the first download unless you clear the cache.

## Bot Flow

1. User starts the bot (`/start`)
2. User selects language (Russian or English)
3. User chooses a university
4. User selects message type
5. User writes a message
   - Clean messages go directly to the queue
   - Messages with profanity are filtered and sent for moderation
   - Media files are always sent for moderation
6. Approved messages are published in the university's channel
7. Users receive notifications when their messages are published

## Admin Commands

- Администраторы и модераторы могут проверять очередь модерации из панели.

---

Created by ShadowX Team
