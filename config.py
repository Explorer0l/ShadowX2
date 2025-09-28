"""
Configuration file for ShadowX Bot
Contains tokens, IDs, and other configuration settings
"""

import os
import re
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

# Bot token (required)
_raw_token = os.environ.get("BOT_TOKEN", "")
TOKEN = _raw_token.strip().strip('"').strip("'")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Create .env with BOT_TOKEN=... or set environment variable.")
# Basic format validation to catch quotes/whitespace issues early
if not re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", TOKEN):
    raise RuntimeError("BOT_TOKEN format looks invalid. Remove quotes/spaces in .env: BOT_TOKEN=12345:ABC... (no quotes)")

# Admin configuration (IDs/usernames from env)
def _parse_int_list(value: str) -> list[int]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace(';', ',').replace('\n', ',').replace('\t', ',').split(',')]
    result = []
    for p in parts:
        if not p:
            continue
        try:
            result.append(int(p))
        except ValueError:
            # Allow space-separated lists too
            for token in p.split():
                try:
                    result.append(int(token.strip()))
                except Exception:
                    continue
    # de-duplicate preserving order
    seen = set()
    ordered = []
    for x in result:
        if x not in seen:
            seen.add(x)
            ordered.append(x)
    return ordered

def _parse_usernames_map(value: str) -> dict[int, str]:
    mapping: dict[int, str] = {}
    if not value:
        return mapping
    # Format: "633:id_username,569:other" or "6336309736:@name,5694951691:@name2"
    # Also accept newlines/semicolons
    items = [x.strip() for x in value.replace('\n', ',').replace(';', ',').split(',') if x.strip()]
    for item in items:
        if ':' in item:
            key, val = item.split(':', 1)
        elif '=' in item:
            key, val = item.split('=', 1)
        else:
            continue
        try:
            uid = int(key.strip())
        except Exception:
            continue
        mapping[uid] = val.strip()
    return mapping

def _parse_str_list(value: str) -> list[str]:
    if not value:
        return []
    parts = [p.strip().lower() for p in value.replace(';', ',').replace('\n', ',').split(',')]
    return [p for p in parts if p]

# Backwards compatible primary admin (optional)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) or None
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '') or None

# Multiple admins support via env list
_ENV_ADMIN_IDS = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = _parse_int_list(_ENV_ADMIN_IDS) or ([ADMIN_ID] if ADMIN_ID else [])

# Admin usernames for display (optional map)
ADMIN_USERNAMES = _parse_usernames_map(os.getenv('ADMIN_USERNAMES', ''))

# Helper function to check if user is admin
def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

# Universities and their channels
UNIVERSITIES = {
    "XIAMEN": "@shadow_xiamen_talk"
}

# Message types and their hashtags (English-only)
MESSAGE_TYPES = {
    "🆘Support🆘": "❗️❗️❗️#NeedHelp❗️❗️❗️",
    "📩Regular message📩": "",
    "💞Confession💞": "💞#AttentionConfession💞"
}

# Queue settings - pacing for outgoing posts (safer defaults; override via env)
# Recommended defaults: 20–30 seconds to avoid flood limits in channels
MESSAGE_QUEUE_MIN_INTERVAL = int(os.getenv("MESSAGE_QUEUE_MIN_INTERVAL", "5"))
MESSAGE_QUEUE_MAX_INTERVAL = int(os.getenv("MESSAGE_QUEUE_MAX_INTERVAL", "8"))
# Backward-compat fallback (unused by new scheduler, kept for compatibility)
MESSAGE_QUEUE_INTERVAL = 45

# Performance settings
MAX_CONCURRENT_MESSAGES = 10  # Process multiple messages concurrently
DB_CONNECTION_POOL_SIZE = 20  # SQLite connection pool
AI_BATCH_SIZE = 5  # Batch AI requests for efficiency

# AI profanity detection (optional). Heavy deps are disabled by default.
# Enable by setting env AI_PROFANITY_ENABLED=1 when AI extras are installed.
AI_PROFANITY_ENABLED = os.getenv("AI_PROFANITY_ENABLED", "1") in ("1", "true", "True", "yes", "on")
AI_PROFANITY_MODEL = os.getenv("AI_PROFANITY_MODEL", "cointegrated/rubert-tiny-toxicity")
# Default to lightweight local rules; switch to 'ensemble' only if you install models
AI_PROFANITY_BACKEND = os.getenv("AI_BACKEND", "ensemble")
AI_LANG_ROUTING = True  # try to detect language and route models
AI_PROFANITY_THRESHOLD = float(os.getenv("AI_PROFANITY_THRESHOLD", "0.7"))  # optimized threshold
AI_PROFANITY_DETECTION_ONLY = False  # combine AI + rules
# Performance optimizations
AI_USE_ASYNC = True  # Use async AI processing to avoid blocking
AI_CACHE_SIZE = 1000  # Cache recent AI results

# Enable translation-assisted auxiliary scoring for Central Asian languages (ky/uz/kk/tg)
AI_PROFANITY_TRANSLATE_AUX = os.getenv("AI_PROFANITY_TRANSLATE_AUX", "1") in ("1", "true", "True", "yes", "on")

# Translation settings
# Enable automatic translation of user content to English on publish
AUTO_TRANSLATE_ENABLED = os.getenv("AUTO_TRANSLATE_ENABLED", "1") in ("1", "true", "True", "yes", "on")
# Translate all non-English messages regardless of source list
AUTO_TRANSLATE_ALL = os.getenv("AUTO_TRANSLATE_ALL", "0") in ("1", "true", "True", "yes", "on")
# Comma-separated ISO-639-1 language codes to force-translate to English
# ru, tg (Tajik), kk (Kazakh), zh (Chinese), uz (Uzbek), ky (Kyrgyz),
# ar (Arabic), hi (Hindi)
AUTO_TRANSLATE_SOURCE_LANGS = [x.strip().lower() for x in os.getenv(
    "AUTO_TRANSLATE_SOURCE_LANGS",
    # Include likely misclassifications for Tajik texts (sr, mk, fa)
    # and add Arabic/Hindi by default
    "ru,tg,kk,zh,uz,ky,ar,hi,sr,mk,fa"
).split(',') if x.strip()]
TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "azure")  # auto|azure|google|libre|deepl|none
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "")
# Optional: DeepL API key to use high-quality translations when available
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

# Azure Cognitive Services Translator (recommended for higher accuracy across CIS/Asian languages)
# Set these to enable Azure provider: TRANSLATION_PROVIDER=azure or TRANSLATION_PROVIDER=auto
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY", "")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "")  # e.g., eastus, westeurope
AZURE_TRANSLATOR_ENDPOINT = os.getenv(
    "AZURE_TRANSLATOR_ENDPOINT",
    "https://api.cognitive.microsofttranslator.com"
)

# English profanity model (HF) to complement RU model
AI_EN_PROFANITY_MODEL = os.getenv("AI_EN_PROFANITY_MODEL", "unitary/unbiased-toxic-roberta")

# AI Spam detection settings (optional)
AI_SPAM_ENABLED = os.getenv("AI_SPAM_ENABLED", "1") in ("1", "true", "True", "yes", "on")
AI_SPAM_MODEL = os.getenv("AI_SPAM_MODEL", "mrm8488/bert-tiny-finetuned-sms-spam-detection")
try:
    # Slightly stricter by default to catch borderline spam
    AI_SPAM_THRESHOLD = float(os.getenv("AI_SPAM_THRESHOLD", "0.7"))
except Exception:
    AI_SPAM_THRESHOLD = 0.7

# Poll settings
POLL_IS_ANONYMOUS = os.getenv("POLL_IS_ANONYMOUS", "1") in ("1", "true", "True", "yes", "on")
POLL_ALLOWS_MULTIPLE = os.getenv("POLL_MULTIPLE", "0") in ("1", "true", "True", "yes", "on")

# Spam detection config
SPAM_ENABLED = True
# Tighten heuristic spam threshold a bit
SPAM_SCORE_THRESHOLD = float(os.getenv("SPAM_SCORE_THRESHOLD", "0.55"))
SPAM_DOMAIN_WHITELIST = _parse_str_list(os.getenv("SPAM_DOMAIN_WHITELIST", ""))
SPAM_HANDLE_WHITELIST = _parse_str_list(os.getenv("SPAM_HANDLE_WHITELIST", ""))

# Minimal words requirement for user messages/captions
MIN_MESSAGE_WORDS = int(os.getenv("MIN_MESSAGE_WORDS", "4"))

# Database settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Allow overriding DB path via env for containerized/hosted deployments
DATABASE_NAME = os.path.abspath(os.getenv('DB_PATH') or os.path.join(BASE_DIR, 'bot_database.db'))