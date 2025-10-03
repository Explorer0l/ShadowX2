"""
Filters module for ShadowX Bot
Contains text filtering functions for profanity and ad detection
"""

import re, os, asyncio, logging
from typing import Iterable, List, Dict

# Import AI-related settings from config, but be resilient during build-time prefetch
# when BOT_TOKEN may be intentionally absent. Fallback to env/defaults in that case.
try:
    from config import (
        AI_PROFANITY_ENABLED, AI_PROFANITY_MODEL, AI_PROFANITY_BACKEND,
        AI_LANG_ROUTING, AI_PROFANITY_THRESHOLD, AI_PROFANITY_DETECTION_ONLY,
        AI_EN_PROFANITY_MODEL, AI_SPAM_ENABLED, AI_SPAM_MODEL, AI_SPAM_THRESHOLD,
        AI_PROFANITY_TRANSLATE_AUX
    )
except Exception:
    AI_PROFANITY_ENABLED = os.getenv("AI_PROFANITY_ENABLED", "0") in ("1", "true", "True", "yes", "on")
    AI_PROFANITY_MODEL = os.getenv("AI_PROFANITY_MODEL", "cointegrated/rubert-tiny-toxicity")
    AI_PROFANITY_BACKEND = os.getenv("AI_BACKEND", "ensemble")
    AI_LANG_ROUTING = True
    try:
        AI_PROFANITY_THRESHOLD = float(os.getenv("AI_PROFANITY_THRESHOLD", "0.7"))
    except Exception:
        AI_PROFANITY_THRESHOLD = 0.7
    AI_PROFANITY_DETECTION_ONLY = False
    AI_EN_PROFANITY_MODEL = os.getenv("AI_EN_PROFANITY_MODEL", "unitary/unbiased-toxic-roberta")
    AI_SPAM_ENABLED = os.getenv("AI_SPAM_ENABLED", "1") in ("1", "true", "True", "yes", "on")
    AI_SPAM_MODEL = os.getenv("AI_SPAM_MODEL", "mrm8488/bert-tiny-finetuned-sms-spam-detection")
    try:
        AI_SPAM_THRESHOLD = float(os.getenv("AI_SPAM_THRESHOLD", "0.75"))
    except Exception:
        AI_SPAM_THRESHOLD = 0.75
    AI_PROFANITY_TRANSLATE_AUX = os.getenv("AI_PROFANITY_TRANSLATE_AUX", "1") in ("1", "true", "True", "yes", "on")

# Safe defaults for optional config
try:
    from config import SPAM_ENABLED, SPAM_SCORE_THRESHOLD, SPAM_DOMAIN_WHITELIST, SPAM_HANDLE_WHITELIST
except Exception:
    SPAM_ENABLED, SPAM_SCORE_THRESHOLD = True, 0.6
    SPAM_DOMAIN_WHITELIST = []
    SPAM_HANDLE_WHITELIST = []

# Optimize transformers environment
for key, val in [("TRANSFORMERS_NO_TF", "1"), ("TRANSFORMERS_NO_FLAX", "1"), 
                 ("TRANSFORMERS_NO_TORCHVISION", "1")]:
    os.environ.setdefault(key, val)

# Lists of banned words
BANNED_WORDS = [
    "порно", "секс", "купить", "продать", "оптом", "халяв", "халява",
    "бесплатно", "порнуха", "18+", "интим", "проститу", "шлюх", "секс знакомства", "знакомства для секса",
    "сука", "бля", "хуй", "пизд", "ебан", "гондон", "мудак", "залуп", "долбоеб", "пидр", "пидараз", "пидарас",
    "кер", "кус", "куси оча", "кси оча", "очага гом", "гом", "мегом", "бгом", "далбаеб", "далбен", "гей",
    "ksi", "kus", "ker", "ks", "gom", "megom", "bgom", "dalbaeb", "dolboeb", "pidr", "pidaraz", "pidaras", "eban", "ebat", "porn", "porno",
    "seks", "bla", "blya", "blat", "blyat", "kerm", "блять", "пиздец", "pizdec", "пиздес", "ахуеть", "axuyet", "охует",
    # English
    "fuck", "shit", "bitch", "asshole", "motherfucker", "dick", "pussy", "pusy",
    # UZ (Latin) — obscene/insult stems and common insults
    "sik", "siki", "sikish", "sikaman", "sikdim", "sikdi",
    "kaltak",  # insult
    "eshak",   # insult (donkey)
    "ahmoq", "axmoq",  # stupid
    # RU/TJ common
    "kun","кун", "кунте", "kunte", "kunut", "kusut", "керм", "sex", "петка", "гой", "трахну", "трахать", "traxat", "trahat", "goy", "goydan", "petka",
    "охует", "охуеть", "ахуеть", "ахует", "guh", "гух", "gh", "гх", "гӯҳ", "гҳ", "дерьмо", "говно", "сучка",
    # Рус. глагол с непристойной коннотацией (основные формы)
    "сосать", "сосу", "сосал", "сосала", "сосало", "сосали", "сосешь", "сосёшь", "сосет", "сосёт",
    "сосем", "сосём", "сосете", "сосёте", "сосут", "соси", "сосите",
    # Частые базовые формы, которые могли отсутствовать
    "пизда", "пидор", "пидорас", "пидорасы", "ебать", "ебаться"
]

# Minimal Arabic/Hindi obscene stems for stronger moderation (exact/script match)
# Arabic
BANNED_WORDS += [
    "كس", "كسم", "زب", "شرموطة", "شرموطه", "منيك", "منيكة", "خرا", "لعنة",
]
# Hindi/Devanagari
BANNED_WORDS += [
    "चूत", "चुतिया", "चूतिया", "भोसडी", "मादरचोद", "बहनचोद", "लंड", "लण्ड", "गांड",
]

# Kazakh (Cyrillic) core insults
BANNED_WORDS += [
    "қаншық", "сайқал", "жалап", "жәләп",
]
# Kyrgyz (Cyrillic) core insults
BANNED_WORDS += [
    "канчык", "канчы", "жалап",
]

# Multi-word phrase insults (Kazakh)
_BANNED_PHRASES = [
    "иттің баласы", "сайқал қатын", "шошқа-ит", "шошқа-ит неме", "шошқа-ит сол",
    "байтал қатын", "әкеңнің басы", "атаңның басы", "атаңның қақ шекесі",
    "әкеңнің аузын", "атаңның аузын"
]

AD_RELATED_WORDS = [
    "реклам", "акция", "скидк", "магазин", "доставк", "заказ", "купить", "фуруши", "мефурушум", "мефурушм",
    "продам", "услуги", "распродаж", "только сегодня", "спецпредложени", "reklama", "for sale", "furuxtan", "furuhtan",
    "furushi", "mefurushm", "mefurushum"
]

# Regex-based ad indicators (URLs, @handles, phones, prices, percent discounts)
_AD_REGEXES_RAW = [
    r"(?:https?://|www\.|t\.me/|telegram\.me/)[\w\-./?=&%#]+",
    r"@[a-zA-Z0-9_]{3,}",
    r"\+?\d[\d\s()\-]{7,}\d",  # phone numbers
    r"\b\d{2,}[\s\xa0]?(?:сомони|сом|somoni|som|сум|uzs|₽|руб\.?|rub|usd|\$|€|тенге|тг|kzt|₸)\b",  # prices incl. KZT
    r"\b(?:скидк\w*|акци\w*|промокод)\b\s*\d{1,2}%",  # discounts like скидка 20%
]
_AD_REGEXES = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _AD_REGEXES_RAW]

# Compiled regex patterns for spam detection
_REGEXES = {
    'handle': re.compile(r"@[a-zA-Z0-9_]{3,}"),
    'url': re.compile(r"(?:https?://|www\.|t\.me/|telegram\.me/)[\w\-./?=&%#]+", re.IGNORECASE),
    'phone': re.compile(r"\+?\d[\d\s()\-]{7,}\d"),
    'repeat_char': re.compile(r"(.)\1{3,}"),
    'repeat_word': re.compile(r"\b(\w{2,})\b(?:\W+\1\b){2,}", re.IGNORECASE),
    'emoji': re.compile(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF\U00002700-\U000027BF]", re.UNICODE)
}
_CTA_WORDS = [
    # RU
    "подпис", "перейди", "жми", "нажми", "репост", "выиграй", "розыгрыш", "лотерея",
    "ставки", "бет", "казино", "1xbet", "букмекер", "заработок", "инвестиции", "crypto",
    "крипто", "только сегодня", "успей", "скидк", "промокод", "бонус", "донат", "подпишись",
    # UZ (Latin)
    "chegirma", "aksiya", "arzon", "do'kon", "dokonga", "buyurtma", "sotiladi", "sotuv", "tekinga",
    # KZ (Cyrillic)
    "жеңілдік", "акция", "дүкен", "жеткізу", "сатып алу", "тапсырыс", "арзан",
    # TJ (Cyrillic)
    "эълон", "тахфиф", "аксия", "мағоза", "фармоиш",
    # EN
    "discount", "sale", "subscribe", "click", "win", "lottery", "bonus", "promo",
]

# Domain detection patterns (compiled)
_DOMAIN_REGEXES = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in [
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,24}|xn--[a-z0-9-]{2,59})\b",
    r"\b(?:[a-z0-9\u0400-\u04FF](?:[a-z0-9\u0400-\u04FF-]{0,61}[a-z0-9\u0400-\u04FF])?\.)+(?:[a-z\u0400-\u04FF]{2,24})\b",
    r"\b(?:[a-z0-9-]{1,63}\s*(?:\.|\(dot\)|\[dot\]|\{dot\}|dot|\u2024|\u2027|·)\s*)+(?:[a-z]{2,24}|xn--[a-z0-9-]{2,59})\b",
    r"\b(?:(?:[a-z0-9](?:\s*[a-z0-9-]){0,62})\s*(?:\.|\(dot\)|\[dot\]|\{dot\}|dot|\u2024|\u2027|·)\s*)+(?:[a-z]{2,24}|xn--[a-z0-9-]{2,59})\b"
]]

# Character variants for leet/confusable detection
_CHAR_VARIANTS = {ch: variants for ch, variants in [
    ('a', ['a', 'а', '@', '4']), ('c', ['c', 'с']), ('e', ['e', 'е', '3']), ('h', ['h', 'н']),
    ('i', ['i', '1', '!', '|']), ('k', ['k', 'к']), ('l', ['l', '1', '|']), ('m', ['m', 'м']),
    ('o', ['o', 'о', '0']), ('p', ['p', 'р']), ('s', ['s', '$', '5']), ('t', ['t', 'т', '7']),
    ('x', ['x', 'х']), ('y', ['y', 'у']), ('а', ['а', 'a', '@', '4']), ('с', ['с', 'c']),
    ('е', ['е', 'e', '3']), ('о', ['о', 'o', '0']), ('р', ['р', 'p']), ('х', ['х', 'x']),
    ('у', ['у', 'y']), ('н', ['н', 'h']), ('к', ['к', 'k']), ('м', ['м', 'm']),
    ('т', ['т', 't', '7']), ('л', ['л', 'l', '|', '1'])
] + [(ch, [ch]) for ch in 'bdfgjnqruvwzжёйцчшщыэюя']}


def _build_pattern_from_word(word: str) -> re.Pattern:
    base = re.sub(r"\s+", "", word.lower())
    parts = ["[" + "".join(re.escape(v) for v in _CHAR_VARIANTS.get(ch, [ch])) + "]"
             for ch in base]
    pattern_str = r"(?<!\w)" + r"[\W_]*".join(parts) + r"(?!\w)"
    try:
        return re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
    except re.error:
        return re.compile(re.escape(word), re.IGNORECASE | re.UNICODE)

# Precompile patterns once (prioritize longer words first to avoid partial masking like "пизд" before "пиздец")
# Cache compiled patterns to avoid recompilation
_pattern_cache = {}
_BANNED_WORDS_SORTED = sorted(BANNED_WORDS, key=lambda w: len(re.sub(r"\s+", "", w)), reverse=True)
_BANNED_PATTERNS = [_build_pattern_from_word(w) for w in _BANNED_WORDS_SORTED]
_BANNED_WORDS_SET = set(w.lower() for w in BANNED_WORDS)
# Direct mapping for quick verification of substring hits without scanning all patterns
_BANNED_WORD_TO_PATTERN = {w.lower(): _build_pattern_from_word(w) for w in BANNED_WORDS}

# Allow suffixes after obscene stems (to catch plural/cases: "пизда", "пидоразы", etc.)
_SUFFIX_STEMS = [
    "пизд", "пидор", "пидарас", "ебан", "ебат", "еба", "ёба", "трах", "шлюх",
    # To catch forms like "охуели", "охуенно", "ахуенно", "охуел"
    "охуе", "ахуе", "хуе", "хуй",
    # EN/UZ stems
    "fuck", "shit", "bitch", "sik", "kaltak", "eshak", "ahmoq", "axmoq",
    # RU stronger variants with prefixes
    "заеб", "заёб", "ёб"
]

def _build_suffix_pattern(stem: str) -> re.Pattern:
    base = re.sub(r"\s+", "", stem.lower())
    parts = ["[" + "".join(re.escape(v) for v in _CHAR_VARIANTS.get(ch, [ch])) + "]"
             for ch in base]
    pattern_str = r"(?<!\w)" + r"[\W_]*".join(parts) + r"[\wа-яё]{0,4}"
    try:
        return re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
    except re.error:
        return re.compile(re.escape(stem), re.IGNORECASE | re.UNICODE)

_BANNED_SUFFIX_PATTERNS = [_build_suffix_pattern(s) for s in _SUFFIX_STEMS]

def _build_prefix_suffix_pattern(stem: str) -> re.Pattern:
    base = re.sub(r"\s+", "", stem.lower())
    parts = ["[" + "".join(re.escape(v) for v in _CHAR_VARIANTS.get(ch, [ch])) + "]"
             for ch in base]
    sep = r"[\W_]*"
    # For highly ambiguous stems like 'еб'/'ёб', avoid matching inside words
    # (e.g., 'учёбное'). Require the stem to start at token boundary.
    if base in {"еб", "ёб"}:
        pattern_str = r"(?<!\w)" + sep.join(parts) + r"[\wа-яё]{0,4}"
    else:
        pattern_str = r"(?<!\w)(?:[\wа-яё]{0,3}" + sep + r")?" + sep.join(parts) + r"[\wа-яё]{0,4}"
    try:
        return re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
    except re.error:
        return re.compile(re.escape(stem), re.IGNORECASE | re.UNICODE)

# Prefix-aware list using core stems that often take prefixes like 'за-'
_PREFIX_SENSITIVE_STEMS = [
    "еб", "ёб", "хуе", "хуй", "пизд"
]

# Whitelist of common words that should NOT be filtered
_WHITELIST_WORDS = [
    "тебя", "себя", "меня", "него", "неё", "нему", "ней", "ними", "тебе", "себе", "мне",
    "учеба", "учебе", "учебы", "учебу", "учебой", "учебник", "учебника", "учебнику",
    "потребность", "потребности", "потребностью", "потребностей", "потребностям",
    "требует", "требуется", "требую", "требуешь", "требуем", "требуете", "требовать",
    "ребенок", "ребенка", "ребенку", "ребенком", "ребенке", "ребята", "ребят", "ребятам",
    # кампус-related (to avoid false hits on substrings like "кус")
    "кампус", "кампуса", "кампусу", "в кампусе", "кампусе", "кампусом",
    "кампусный", "кампусная", "кампусное", "кампусной", "кампусном", "кампусные", "кампусных",
    # учеба-related (avoid false hits from stems like 'ёб')
    "учеба", "учёба", "учебный", "учебная", "учебное", "учебной", "учебном", "учебные", "учебных",
    "учёбный", "учёбная", "учёбное", "учёбной", "учёбном", "учёбные", "учёбных"
]

_BANNED_PREFIX_SUFFIX_PATTERNS = [_build_prefix_suffix_pattern(s) for s in _PREFIX_SENSITIVE_STEMS]

# Optimize whitelist membership using a set (case-insensitive)
_WHITELIST_WORDS_SET = set(w.lower() for w in _WHITELIST_WORDS)

def _is_whitelisted_word(word: str) -> bool:
    """Check if a word is in the whitelist and should not be filtered."""
    word_lower = word.lower().strip()
    return word_lower in _WHITELIST_WORDS_SET

# ---- AI Profanity (optional) ----
_ai_available = False
_hf_tokenizer = None
_hf_model = None
_hf_en_tokenizer = None
_hf_en_model = None
_detoxify_available = False
_detoxify_model = None
_spam_model = None
_spam_tokenizer = None
_langid_available = False
_langid_fn = None
_local_available = True  # always available
_device = "cpu"
_device_logged = False

# AI result caching for performance
_ai_cache = {}
_ai_cache_max_size = 1000

def _get_device() -> str:
    """Choose best available device (cuda if available, else cpu)."""
    try:
        import torch  # type: ignore
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"

def _ensure_ai_loaded():
    global _ai_available, _hf_tokenizer, _hf_model, _detoxify_available, _detoxify_model, _langid_available, _langid_fn, _device, _device_logged, _hf_en_model, _hf_en_tokenizer, _spam_model, _spam_tokenizer
    if not AI_PROFANITY_ENABLED:
        return
    # Load HF model/tokenizer directly only when needed (avoid heavy deps otherwise)
    if not _ai_available and AI_PROFANITY_BACKEND in ("hf", "ensemble") and os.environ.get("AI_DISABLE_HF") != "1":
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _hf_tokenizer = AutoTokenizer.from_pretrained(AI_PROFANITY_MODEL)
            _hf_model = AutoModelForSequenceClassification.from_pretrained(AI_PROFANITY_MODEL)
            # Select device and move model
            try:
                import torch  # type: ignore
                _device = _get_device()
                _hf_model.to(_device)
                _hf_model.eval()
            except Exception:
                _device = "cpu"
            # Optional: load PEFT/LoRA adapter if provided
            try:
                adapter_path = os.getenv("AI_LORA_ADAPTER_PATH", "").strip()
                if adapter_path:
                    from peft import PeftModel  # type: ignore
                    _hf_model = PeftModel.from_pretrained(_hf_model, adapter_path)
                    try:
                        import torch  # type: ignore
                        _hf_model.to(_device)
                        _hf_model.eval()
                    except Exception:
                        pass
            except Exception:
                # PEFT not installed or adapter invalid — ignore gracefully
                pass
            _ai_available = True
        except Exception:
            _ai_available = False
            _hf_tokenizer = None
            _hf_model = None
    # Load Detoxify multilingual
    if not _detoxify_available and AI_PROFANITY_BACKEND in ("detoxify", "ensemble"):
        try:
            from detoxify import Detoxify
            # Detoxify accepts device parameter in recent versions
            dev = _get_device()
            try:
                _detoxify_model = Detoxify('multilingual', device=dev)
            except TypeError:
                # Older versions: move internal model manually if torch present
                _detoxify_model = Detoxify('multilingual')
                try:
                    import torch  # type: ignore
                    _detoxify_model.model.to(dev)
                    _detoxify_model.model.eval()
                except Exception:
                    pass
            _detoxify_available = True
        except Exception:
            # Attempt to clean corrupted torch hub cache and retry once
            try:
                _cleanup_detoxify_cache()
                from detoxify import Detoxify  # retry import
                dev = _get_device()
                try:
                    _detoxify_model = Detoxify('multilingual', device=dev)
                except TypeError:
                    _detoxify_model = Detoxify('multilingual')
                    try:
                        import torch  # type: ignore
                        _detoxify_model.model.to(dev)
                        _detoxify_model.model.eval()
                    except Exception:
                        pass
                _detoxify_available = True
            except Exception:
                # Optional: fallback to smaller English models (may trigger TF deps). Enable via env AI_ALLOW_DETOXIFY_SMALL=1
                if os.environ.get("AI_ALLOW_DETOXIFY_SMALL") == "1":
                    try:
                        from detoxify import Detoxify
                        for model_type in ("unbiased-small", "original-small", "unbiased", "original"):
                            try:
                                _detoxify_model = Detoxify(model_type)
                                _detoxify_available = True
                                break
                            except Exception:
                                continue
                        if not _detoxify_available:
                            _detoxify_model = None
                    except Exception:
                        _detoxify_available = False
                        _detoxify_model = None
                else:
                    _detoxify_available = False
                    _detoxify_model = None
    # Load lightweight langid
    if not _langid_available and AI_LANG_ROUTING:
        try:
            import langid
            _langid_fn = langid.classify
            _langid_available = True
        except Exception:
            _langid_available = False
            _langid_fn = None

    # One-time device log for visibility
    if not _device_logged:
        _device_logged = True
        try:
            import torch  # type: ignore
            print(f"AI moderation device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
        except Exception:
            logging.info("AI moderation device: CPU")

    # Load English HF toxicity model
    if _hf_en_model is None and _hf_en_tokenizer is None and AI_PROFANITY_BACKEND in ("hf", "ensemble") and os.environ.get("AI_DISABLE_HF") != "1":
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _hf_en_tokenizer = AutoTokenizer.from_pretrained(AI_EN_PROFANITY_MODEL)
            _hf_en_model = AutoModelForSequenceClassification.from_pretrained(AI_EN_PROFANITY_MODEL)
            try:
                import torch  # type: ignore
                dev = _get_device()
                _hf_en_model.to(dev)
                _hf_en_model.eval()
            except Exception:
                pass
        except Exception:
            _hf_en_model = None
            _hf_en_tokenizer = None

    # Load spam model
    if AI_SPAM_ENABLED and _spam_model is None:
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _spam_tokenizer = AutoTokenizer.from_pretrained(AI_SPAM_MODEL)
            _spam_model = AutoModelForSequenceClassification.from_pretrained(AI_SPAM_MODEL)
            try:
                import torch  # type: ignore
                dev = _get_device()
                _spam_model.to(dev)
                _spam_model.eval()
            except Exception:
                pass
        except Exception:
            _spam_model = None
            _spam_tokenizer = None

async def ai_profanity_score_async(text: str) -> float:
    """Async version of profanity scoring to avoid blocking the event loop.
    Return toxicity/profanity score (0..1). Uses several heads if available.
    Falls back to 0 if AI is disabled/unavailable.
    """
    if not text or not AI_PROFANITY_ENABLED:
        return 0.0
    
    # Check cache first
    text_hash = hash(text.lower().strip())
    if text_hash in _ai_cache:
        return _ai_cache[text_hash]
    
    _ensure_ai_loaded()
    
    # Run CPU-intensive AI inference in thread pool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    score = await loop.run_in_executor(None, _ai_profanity_score_sync, text)

    # Optional translation-assisted auxiliary scoring for Central Asian langs
    if AI_PROFANITY_TRANSLATE_AUX and AI_PROFANITY_ENABLED:
        try:
            # Light language gating to avoid unnecessary calls
            lang = None
            if AI_LANG_ROUTING:
                try:
                    import langid  # type: ignore
                    lang, _ = langid.classify(text)
                except Exception:
                    lang = None
            # Heuristics for Cyrillic-specific letters to correct misclassifications
            t = text or ""
            tajik_chars = set('ҳҲӣӢӯӮғҒқҚҷҶ')
            ky_chars = set('өӨүҮңҢ')
            kk_chars = set('әӘғҒқҚңҢұҰүҮһҺіІ')
            if lang is None:
                if any(ch in tajik_chars for ch in t):
                    lang = 'tg'
                elif any(ch in ky_chars for ch in t):
                    lang = 'ky'
                elif any(ch in kk_chars for ch in t):
                    lang = 'kk'
            if lang in {'ky', 'uz', 'kk', 'tg'} or _looks_uzbek_latin(text):
                # Translate to English and score with EN model as auxiliary signal
                try:
                    from utils.translate import translate_to_en, detect_language  # lazy import
                    detected = None
                    try:
                        detected = await detect_language(text)
                    except Exception:
                        detected = lang
                    translated, provider = await translate_to_en(text, detected_lang=detected)
                    if translated and isinstance(translated, str) and translated.strip() and translated.strip().lower() != (text or '').strip().lower():
                        # Score translated text with EN model in executor
                        en_score = await loop.run_in_executor(None, _ai_en_profanity_score_sync, translated)
                        score = max(score, en_score)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Cache result (with size limit)
    if len(_ai_cache) >= _ai_cache_max_size:
        # Remove oldest entries (simple FIFO)
        keys_to_remove = list(_ai_cache.keys())[:100]
        for k in keys_to_remove:
            del _ai_cache[k]
    _ai_cache[text_hash] = score
    
    return score

def _ai_profanity_score_sync(text: str) -> float:
    """Synchronous AI scoring implementation (for thread pool execution)."""
    # Optional language routing for specialized models
    lang = None
    if _langid_available and AI_LANG_ROUTING:
        try:
            lang, _ = _langid_fn(text)
        except Exception:
            lang = None

    scores = []

    # Local lightweight scorer using our patterns (no external deps)
    if AI_PROFANITY_BACKEND in ("local", "ensemble"):
        try:
            # Count matches and coverage over letters/digits
            total_letters = len(re.sub(r"[\W_]+", "", text or "")) or 1
            match_letters = 0
            match_count = 0
            strong_hit = False
            # Strong stems imply higher toxicity
            strong_stems = ("пизд", "хуй", "хуе", "охуе", "ахуе", "заеб", "заёб", "ебат", "ебан", "еба", "ёба", "пидор", "пидарас", "сука", "бля", "блять", "трах", "шлюх")

            # Scan banned exact patterns
            for pat in _BANNED_PATTERNS:
                for m in pat.finditer(text):
                    span = m.group(0)
                    letters = len(re.sub(r"[\W_]+", "", span))
                    if letters:
                        match_letters += letters
                        match_count += 1
                        lower = span.lower()
                        if any(stem in lower for stem in strong_stems):
                            strong_hit = True
            # Scan suffix patterns
            suffix_hit = False
            for pat in _BANNED_SUFFIX_PATTERNS:
                m = pat.search(text)
                if m:
                    suffix_hit = True
                    span = m.group(0)
                    letters = len(re.sub(r"[\W_]+", "", span))
                    match_letters += letters
                    match_count += 1
            # Scan prefix-aware patterns
            for pat in _BANNED_PREFIX_SUFFIX_PATTERNS:
                m = pat.search(text)
                if m:
                    suffix_hit = True
                    span = m.group(0)
                    letters = len(re.sub(r"[\W_]+", "", span))
                    match_letters += letters
                    match_count += 1

            coverage = min(1.0, match_letters / max(1, total_letters))
            score = 0.0
            if match_count >= 1:
                score += 0.35
            if match_count >= 2:
                score += 0.15
            score += min(0.5, coverage)
            if strong_hit:
                score = max(score, 0.7)
            if suffix_hit:
                score += 0.15
            score = max(0.0, min(1.0, score))
            scores.append(float(score))
        except Exception:
            pass

    # HF RU model (PyTorch direct), robust to missing TF
    if _ai_available and _hf_model is not None and _hf_tokenizer is not None and AI_PROFANITY_BACKEND in ("hf", "ensemble") and os.environ.get("AI_DISABLE_HF") != "1":
        try:
            import torch
            best = 0.0
            # Prefer Slavic/Cyrillic languages but don't hard-block scoring
            allowed_langs = {"ru", "uk", "be", "kk", "tg", "tj", "uz", "tt"}
            variants = _normalized_variants_for_ai(text) if (lang is None or lang in allowed_langs) else [text]
            if variants:
                for variant in variants:
                    tokens = _hf_tokenizer(variant, return_tensors="pt", truncation=True, max_length=256)
                    # Move to same device as model
                    try:
                        tokens = {k: v.to(_device) for k, v in tokens.items()}
                    except Exception:
                        pass
                    with torch.no_grad():
                        outputs = _hf_model(**tokens)
                        logits = outputs.logits.squeeze(0)
                        probs = torch.sigmoid(logits).detach().cpu().tolist()
                    id2label = getattr(_hf_model.config, "id2label", {}) or {}
                    label_probs = {}
                    for idx, p in enumerate(probs):
                        # Support id2label with string keys ("0") or int keys (0)
                        raw = id2label.get(idx, None)
                        if raw is None:
                            raw = id2label.get(str(idx), idx)
                        label_name = str(raw).lower()
                        label_probs[label_name] = float(p)
                    # Focus on explicit profanity/insults, but provide robust fallbacks
                    # Include 'obscenity' to match RU model label names
                    preferred_labels = ("obscene", "obscenity", "insult", "swear", "profan")
                    var_best = 0.0
                    for label, p in label_probs.items():
                        if any(label_key in label for label_key in preferred_labels):
                            var_best = max(var_best, p)
                    if var_best == 0.0:
                        # Conservative fallback: consider 'toxic/oxicity' first if present
                        fallback_keys = ("toxic", "toxicity")
                        for label, p in label_probs.items():
                            if any(k in label for k in fallback_keys):
                                var_best = max(var_best, p)
                    if var_best == 0.0 and label_probs:
                        # Ultimate fallback: take the max probability among all labels
                        var_best = max(label_probs.values())
                    best = max(best, var_best)
            scores.append(best)
        except Exception:
            pass

    # Detoxify multilingual (XLM‑R); helpful for TJ/UZ/KZ/EN
    if _detoxify_available and _detoxify_model is not None and AI_PROFANITY_BACKEND in ("detoxify", "ensemble"):
        try:
            keys = ["obscene", "insult", "toxicity", "severe_toxicity", "threat", "identity_attack"]
            best = 0.0
            for variant in _normalized_variants_for_ai(text):
                # Process long texts in chunks to avoid truncation effects
                for chunk in _chunks_for_ai(variant, max_len=250):
                    out = _detoxify_model.predict(chunk)
                    best = max(best, max(float(out.get(k, 0.0)) for k in keys))
            scores.append(best)
        except Exception:
            pass

    if not scores:
        return 0.0
    # Ensemble: max-of-experts for safety (we’d rather over-moderate than пропустить)
    return max(scores)

def _ai_en_profanity_score_sync(text: str) -> float:
    """English-only toxicity score using HF EN model."""
    if _hf_en_model is None or _hf_en_tokenizer is None:
        return 0.0
    try:
        import torch  # type: ignore
        tokens = _hf_en_tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        try:
            dev = _get_device()
            tokens = {k: v.to(dev) for k, v in tokens.items()}
        except Exception:
            pass
        with torch.no_grad():
            logits = _hf_en_model(**tokens).logits.squeeze(0)
            probs = torch.sigmoid(logits).detach().cpu().tolist()
        return float(max(probs)) if probs else 0.0
    except Exception:
        return 0.0

def _ai_spam_score_sync(text: str) -> float:
    """Spam probability using small HF model; returns 0..1."""
    if not AI_SPAM_ENABLED or _spam_model is None or _spam_tokenizer is None:
        return 0.0
    try:
        import torch  # type: ignore
        tokens = _spam_tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        try:
            dev = _get_device()
            tokens = {k: v.to(dev) for k, v in tokens.items()}
        except Exception:
            pass
        with torch.no_grad():
            logits = _spam_model(**tokens).logits.squeeze(0)
            probs = torch.softmax(logits, dim=-1).detach().cpu().tolist()
        if len(probs) >= 2:
            return float(probs[1])
        return float(max(probs)) if probs else 0.0
    except Exception:
        return 0.0

def ai_profanity_score(text: str) -> float:
    """Synchronous wrapper that ensures models are loaded before scoring."""
    try:
        _ensure_ai_loaded()
    except Exception:
        pass
    # Route EN texts to EN model as primary, combine with ensemble for safety
    try:
        lang = None
        if AI_LANG_ROUTING:
            import langid  # type: ignore
            lang, _ = langid.classify(text)
        if lang == 'en':
            en_score = _ai_en_profanity_score_sync(text)
            return max(en_score, _ai_profanity_score_sync(text))
    except Exception:
        pass
    return _ai_profanity_score_sync(text)

def ai_contains_profanity(text: str) -> bool:
    threshold = _lang_adjusted_threshold(text)
    return ai_profanity_score(text) >= threshold

async def ai_contains_profanity_async(text: str) -> bool:
    score = await ai_profanity_score_async(text)
    threshold = _lang_adjusted_threshold(text)
    return score >= threshold

def contains_banned_words(text):
    """Check if text contains banned words (robust against separators/leet/confusables)."""
    if not text:
        return False
    # If AI-only mode for detection, skip manual lists
    if AI_PROFANITY_ENABLED and AI_PROFANITY_DETECTION_ONLY:
        return ai_contains_profanity(text)
    
    # Check if any words in the text are whitelisted
    words = re.findall(r'\b\w+\b', text.lower())
    if any(_is_whitelisted_word(word) for word in words):
        # Replace all whitelisted words in one pass using a precompiled regex
        global _WHITELIST_REGEX
        try:
            _ = _WHITELIST_REGEX  # type: ignore[name-defined]
        except NameError:
            # Build lazily to avoid cost on import
            if _WHITELIST_WORDS_SET:
                pattern = r"\\b(?:" + "|".join(re.escape(w) for w in sorted(_WHITELIST_WORDS_SET, key=len, reverse=True)) + r")\\b"
                _WHITELIST_REGEX = re.compile(pattern, re.IGNORECASE)
            else:
                _WHITELIST_REGEX = re.compile(r"(?!x)x")  # never matches
        temp_text = _WHITELIST_REGEX.sub('__SAFE__', text)
        # Check the text without whitelisted words
        return _check_patterns_only(temp_text)
    
    # No whitelisted words found, proceed with normal checking
    return _check_patterns_only(text)

def _check_patterns_only(text):
    """Helper function to check patterns without whitelist consideration."""
    if not text or text.strip() == '__SAFE__':
        return False
        
    # Fast path: check exact word matches first (most common case)
    text_lower = text.lower()
    # Narrow verification only to words that actually appear as substrings
    hits = [w for w in _BANNED_WORDS_SET if w in text_lower]
    for w in hits:
        pat = _BANNED_WORD_TO_PATTERN.get(w)
        if pat and pat.search(text):
            return True
    
    # Full pattern matching if no quick hits
    for pat in _BANNED_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    for pat in _BANNED_PREFIX_SUFFIX_PATTERNS:
        if pat.search(text):
            return True

    # Phrase-level checks (exact match ignoring extra spaces/case/hyphens between tokens)
    try:
        t_norm = re.sub(r"\s+", " ", text.lower()).strip()
        t_norm = t_norm.replace("-", "-")
        for phrase in _BANNED_PHRASES:
            p = re.sub(r"\s+", " ", phrase.lower()).strip()
            if p and p in t_norm:
                return True
    except Exception:
        pass
    
    # AI layer (optional, language-aware thresholds)
    if AI_PROFANITY_ENABLED:
        try:
            thr = _lang_adjusted_threshold(text)
            if ai_profanity_score(text) >= thr:
                return True
        except Exception:
            pass
    return False

async def contains_banned_words_async(text):
    """Async version of profanity detection for high-load scenarios."""
    if not text:
        return False
    # If AI-only mode for detection, skip manual lists
    if AI_PROFANITY_ENABLED and AI_PROFANITY_DETECTION_ONLY:
        return await ai_contains_profanity_async(text)
    
    # Fast synchronous checks first
    text_lower = text.lower()
    hits = [w for w in _BANNED_WORDS_SET if w in text_lower]
    for w in hits:
        pat = _BANNED_WORD_TO_PATTERN.get(w)
        if pat and pat.search(text):
            return True
    
    for pat in _BANNED_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    for pat in _BANNED_PREFIX_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    
    # AI layer (async to avoid blocking, language-aware thresholds)
    if AI_PROFANITY_ENABLED:
        try:
            score = await ai_profanity_score_async(text)
            thr = _lang_adjusted_threshold(text)
            if score >= thr:
                return True
        except Exception:
            pass
    return False

def contains_ad_words(text):
    """Check if text contains advertising-related words (respects whitelist) with relaxed logic for simple classifieds and benign words.
    We avoid flagging simple intent-only phrases like "продаю", "куплю", "продам", and benign logistics/purchase words like
    "доставка", "заказ", "заказал", "купил" when there are no links/handles/phones/prices/discounts/CTA.
    """
    if not text: return False
    text_lower = text.lower()
    # If only whitelisted domains/handles are present and no other ad signals, return False
    w_domains, w_handles = _is_whitelisted_domain_or_handle(text_lower)

    has_url = bool(_REGEXES['url'].search(text_lower))
    has_handle = bool(_REGEXES['handle'].search(text_lower))
    has_phone = bool(_REGEXES['phone'].search(text_lower))
    has_domain = any(rx.search(text) for rx in _DOMAIN_REGEXES)
    has_ad_regex = any(rx.search(text_lower) for rx in _AD_REGEXES)
    has_words = any(word in text_lower for word in AD_RELATED_WORDS)

    # Price and discount (explicit patterns)
    try:
        _price_rx = re.compile(r"\b\d{2,}[\s\xa0]?(?:сомони|сом|somoni|som|сум|uzs|₽|руб\.?|rub|usd|\$|€|тенге|тг|kzt|₸)\b", re.IGNORECASE)
        _discount_rx = re.compile(r"\b(?:скидк\w*|акци\w*|промокод)\b\s*\d{1,2}%?", re.IGNORECASE)
    except Exception:
        _price_rx = _discount_rx = None
    has_price = bool(_price_rx.search(text_lower)) if _price_rx else False
    has_discount = bool(_discount_rx.search(text_lower)) if _discount_rx else False
    cta_hits = sum(1 for w in _CTA_WORDS if w in text_lower)

    strong_ad = has_url or has_domain or has_handle or has_phone or has_price or has_discount or (cta_hits > 0)

    # Relaxation: treat bare intent words and benign shopping/logistics words as non-ads unless combined with strong signals
    simple_intents = ("продаю", "куплю", "ищу", "продам")
    benign_stems = ("доставк", "заказ", "заказал", "заказала", "заказано", "купил", "купила", "купили")
    has_bare_intent = any(w in text_lower for w in simple_intents)
    has_benign_only = any(stem in text_lower for stem in benign_stems)
    if (has_bare_intent or has_benign_only) and not strong_ad:
        has_words = False

    if (has_domain or has_url or has_handle) and not has_words:
        # If all links/handles belong to whitelist, ignore
        if w_domains or w_handles:
            # Check if removing whitelisted tokens eliminates ad signals
            clean = text_lower
            for d in SPAM_DOMAIN_WHITELIST:
                clean = clean.replace(d, "")
            for h in SPAM_HANDLE_WHITELIST:
                clean = clean.replace('@' + h.lstrip('@'), "")
            if not any(rx.search(clean) for rx in _AD_REGEXES) and not any(rx.search(clean) for rx in _DOMAIN_REGEXES):
                return False
    return has_ad_regex or has_domain or has_words or has_url or has_handle or has_phone or has_price or has_discount


def _is_whitelisted_domain_or_handle(text: str) -> tuple[int, int]:
    """Return counts of whitelisted domains and handles present in text."""
    if not text:
        return 0, 0
    lower = text.lower()
    # Simple substring match is acceptable because we also use regexes for scoring
    domain_hits = sum(1 for d in SPAM_DOMAIN_WHITELIST if d and d in lower)
    handle_hits = sum(1 for h in SPAM_HANDLE_WHITELIST if h and (('@' + h.lstrip('@')) in lower))
    return domain_hits, handle_hits

def spam_score(text: str) -> float:
    """Return spam score (0..1) using lightweight heuristics."""
    if not text: return 0.0
    t = text.strip()
    # Normalize by removing zero-width obfuscation characters
    try:
        t = _strip_zero_width(t)
    except Exception:
        pass
    score = 0.0
    
    # Determine script dominance once (used in multiple heuristics)
    try:
        cyr_letters_global = re.findall(r"[А-Яа-яЁё]", t)
        lat_letters_global = re.findall(r"[A-Za-z]", t)
        is_cyr_dom = len(cyr_letters_global) > len(lat_letters_global) * 1.5
    except Exception:
        is_cyr_dom = False
    
    # Count various spam indicators
    counts = {k: len(v.findall(t)) for k, v in _REGEXES.items() if k in ['url', 'handle', 'phone']}
    # Apply whitelist reductions
    w_domains, w_handles = _is_whitelisted_domain_or_handle(t)
    if w_domains:
        # Reduce domain/url impact proportionally to whitelisted hits
        counts['url'] = max(0, counts.get('url', 0) - w_domains)
        # Also reduce domain regex hits later via ad_hits by adjusting ad_hits below
    if w_handles:
        counts['handle'] = max(0, counts.get('handle', 0) - w_handles)
    domain_hits = sum(len(rx.findall(t)) for rx in _DOMAIN_REGEXES)
    ad_hits = sum(1 for rx in _AD_REGEXES if rx.search(t))
    if w_domains:
        ad_hits = max(0, ad_hits - w_domains)
    
    # Calculate scores
    score += min(0.5, 0.25 * counts['url']) + min(0.4, 0.2 * domain_hits)
    score += min(0.4, 0.2 * counts['handle']) + min(0.6, 0.3 * counts['phone'])
    score += min(0.4, 0.2 * ad_hits) if ad_hits else 0
    score += min(0.4, 0.2 * len(_REGEXES['repeat_char'].findall(t)))
    score += 0.25 if _REGEXES['repeat_word'].search(t) else 0
    
    # Emoji and case analysis
    emojis = len(_REGEXES['emoji'].findall(t))
    emoji_ratio = emojis / max(1, len(t))
    score += 0.5 if emoji_ratio > 0.4 else (0.3 if emoji_ratio > 0.2 else 0)
    
    alpha = [c for c in t if c.isalpha()]
    if alpha and len(alpha) >= 10:
        upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
        score += 0.2 if upper_ratio > 0.7 else 0
    
    # CTA words and low-content detection
    cta_hits = sum(1 for w in _CTA_WORDS if w in t.lower())
    score += min(0.6, 0.2 * cta_hits) if cta_hits else 0
    
    letters_only = len(re.sub(r"[^A-Za-zА-Яа-яЁё0-9]", "", t))
    score += 0.6 if letters_only < 6 and counts['url'] else 0

    # NEW: gibberish / random numbers heavy
    # - very high digit ratio
    digits = sum(ch.isdigit() for ch in t)
    alnum = sum(ch.isalnum() for ch in t) or 1
    digit_ratio = digits / alnum
    if digit_ratio > 0.6 and len(t) > 15:
        score += 0.4

    # - long runs of alternating space/word length = 1-2 (e.g., "1 2 3 4 235 325")
    short_tokens = re.findall(r"\b[\w\d]{1,2}\b", t)
    # For long texts, short tokens are more natural (prepositions, particles)
    threshold = (10 if is_cyr_dom else 8) if len(t) > 600 else (8 if is_cyr_dom else 6)
    if len(short_tokens) >= threshold:
        base_short = min(0.5, 0.05 * len(short_tokens))
        score += base_short * (0.3 if is_cyr_dom else 1.0)

    # - low vowel ratio heuristic (latin/cyrillic)
    vowels = re.findall(r"[aeiouyаеёиоуыэюяAEIOUYАЕЁИОУЫЭЮЯ]", t)
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", t)
    if letters:
        vowel_ratio = len(vowels) / max(1, len(letters))
        if vowel_ratio < 0.22 and len(letters) >= 12:
            score += 0.3

    # - low alphanumeric ratio (too many symbols/noise)
    noise = sum(1 for ch in t if not ch.isalnum() and not ch.isspace())
    total = len(t)
    if total >= 10:
        # For benign Cyrillic texts (no links/handles/phones/ads/CTA), discount neutral punctuation
        benign_text = (counts.get('url', 0) == 0 and counts.get('handle', 0) == 0 and counts.get('phone', 0) == 0 and ad_hits == 0 and cta_hits == 0)
        if is_cyr_dom and benign_text:
            benign_punct = set("—–-«»“”„\"'.,:;!?()[]{}…")
            noise_benign = sum(1 for ch in t if (not ch.isalnum() and not ch.isspace()) and (ch in benign_punct))
            noise = max(0, noise - int(noise_benign * 0.8))
        noise_ratio = noise / total
        threshold = 0.45 if is_cyr_dom else 0.35
        if noise_ratio > threshold:
            if is_cyr_dom:
                score += min(0.4, 0.2 + (noise_ratio - threshold) * 0.5)
            else:
                score += min(0.6, 0.3 + (noise_ratio - threshold) * 0.8)

    # - leading noisy token: symbol/currency + digits at start
    try:
        if re.match(r"^\s*[^\w\s]{2,}\s*\d{1,5}", t) or re.match(r"^\s*[\(\[\{]?\s*[\$€£¥₽₹]?\s*[+\-]?\d{1,5}", t):
            score += 0.35
    except Exception:
        pass

    # - short-token heavy: many tokens with length <= 2 (attenuate for Cyrillic texts)
    try:
        tokens = re.findall(r"\b\w+\b", t)
        if tokens:
            short_token_count = sum(1 for w in tokens if len(w) <= 2)
            if len(tokens) >= 4:
                short_ratio = short_token_count / len(tokens)
                # For Cyrillic-dominant text, use a higher trigger and lower weight
                trigger = 0.65 if is_cyr_dom else 0.5
                if short_ratio >= trigger:
                    base_bonus = min(0.5, 0.2 + 0.2 * short_ratio)
                    score += base_bonus * (0.45 if is_cyr_dom else 1.0)
            # vowel-less tokens (likely gibberish like "sj", "rjebe")
            vowel_less = 0
            for w in tokens:
                letters_in_w = re.findall(r"[A-Za-zА-Яа-яЁё]", w)
                # Ignore very short tokens when counting vowel-less
                if len(w) <= 2:
                    continue
                if letters_in_w and not re.search(r"[aeiouyаеёиоуыэюяAEIOUYАЕЁИОУЫЭЮЯ]", w):
                    vowel_less += 1
            if vowel_less >= 1:
                # Stronger weight for at least one vowel-less token, additional per extra token
                bonus = min(0.45, 0.15 + 0.1 * max(0, vowel_less - 1))
                # Attenuate for Cyrillic-dominant texts to reduce false positives
                score += bonus * (0.6 if is_cyr_dom else 1.0)
            # mixed-script tokens (latin+cyrillic in same token) often indicate obfuscation
            mixed_script = sum(1 for w in tokens if re.search(r"[A-Za-z]", w) and re.search(r"[А-Яа-яЁё]", w))
            if mixed_script:
                score += min(0.4, 0.2 + 0.1 * max(0, mixed_script - 1))
            if mixed_script and vowel_less:
                # Synergy: both obfuscations present
                # Reduce synergy bonus under Cyrillic-dominant text
                score += 0.05 if is_cyr_dom else 0.1
    except Exception:
        pass

    # - character diversity and repetition ratio
    try:
        unique_chars = len(set(t))
        if len(t) >= 15:
            diversity = unique_chars / len(t)
            # For long texts, diversity naturally decreases; adjust threshold
            threshold = 0.15 if len(t) > 500 else 0.2
            if diversity < threshold:
                # Reduce penalty for Cyrillic texts and long texts
                penalty = 0.15 if is_cyr_dom or len(t) > 800 else 0.3
                score += penalty
        # repeated syllable-like patterns (e.g., 'ла ла ла', 'ала ала ала')
        if re.search(r"(?i)\b([\wа-яё]{2,3})\b(?:\s+\1\b){2,}", t):
            score += 0.35
        # repeated 2-3 letter fragments joined in longer tokens (e.g., талу-тулу-тулу)
        if re.search(r"(?i)([\wа-яё]{2,3}).*\1.*\1", t):
            # Attenuate for Cyrillic-dominant texts (common bigram repetition in RU)
            score += (0.05 if is_cyr_dom else 0.2)
    except Exception:
        pass

    # - consonant cluster heuristic (random latin clusters)
    consonant_runs = re.findall(r"(?i)\b[b-df-hj-np-tv-z]{5,}\b", t)
    if consonant_runs:
        score += min(0.5, 0.1 * sum(len(x) for x in consonant_runs))

    # - language detection uncertainty (very short or unknown)
    try:
        import langid  # type: ignore
        if len(t) >= 8:
            lang, conf = langid.classify(t)
            # If not a real language with decent confidence, bump score
            # Note: langid confidence can be negative for very certain classifications
            conf_threshold = 0.7 if is_cyr_dom else 0.85
            if conf < conf_threshold and conf > -1000 and len(letters) >= 10:
                score += (0.1 if is_cyr_dom else 0.25)
            # Penalize text that looks like random key smash in Latin (q/w/e/r spam)
            if lang == 'en' and re.search(r"(?i)\b[qwertyuiopasdfghjklzxcvbnm]{8,}\b", t):
                score += 0.3
    except Exception:
        pass
    
    return max(0.0, min(1.0, score))

def contains_spam(text: str) -> bool:
    if not SPAM_ENABLED:
        return False
    base = spam_score(text)
    ai = 0.0
    try:
        _ensure_ai_loaded()
        ai = _ai_spam_score_sync(text)
    except Exception:
        ai = 0.0
    # Fast path: require strictly greater than threshold to reduce borderline false positives
    if base > float(SPAM_SCORE_THRESHOLD) or (AI_SPAM_ENABLED and ai > float(AI_SPAM_THRESHOLD)):
        return True
    # Optional: near-duplicate detection against recent DB messages (lightweight)
    try:
        from database import get_recent_message_texts  # lazy import to avoid circulars
        recent = get_recent_message_texts(limit=150)
        if recent:
            import re
            from difflib import SequenceMatcher
            candidate = re.sub(r"\s+", " ", (text or "").strip().lower())[:400]
            if len(candidate) >= 12:
                # Compare with top-N recent short texts for speed
                for ref in recent[:80]:
                    ref_norm = re.sub(r"\s+", " ", (ref or "").strip().lower())[:400]
                    if not ref_norm or ref_norm == candidate:
                        continue
                    # Skip if ref is long and candidate is very short (reduce false hits)
                    if len(ref_norm) > 60 and len(candidate) < 25:
                        continue
                    ratio = SequenceMatcher(a=candidate, b=ref_norm).ratio()
                    if ratio >= 0.92:
                        return True
    except Exception:
        pass
    return False

def filter_profanity(text):
    """Filter profanity from text by replacing matched spans with asterisks.
    Keeps first and last letters visible, masks the middle.
    Robust to separators/leet/confusables.
    """
    if not text:
        return text

    def _mask_middle_only(span: str) -> str:
        """Mask only the middle part, keeping first and last letters visible."""
        alnum_chars = [ch for ch in span if ch.isalnum()]
        if len(alnum_chars) <= 2:
            return "".join('*' if ch.isalnum() else ch for ch in span)
        
        result, alnum_idx = [], 0
        for ch in span:
            if ch.isalnum():
                result.append(ch if alnum_idx in (0, len(alnum_chars) - 1) else '*')
                alnum_idx += 1
            else:
                result.append(ch)
        return ''.join(result)

    def repl(match: re.Match) -> str:
        matched_text = match.group(0)
        # Check if the matched text is a whitelisted word
        if _is_whitelisted_word(matched_text):
            return matched_text  # Don't mask whitelisted words
        return _mask_middle_only(matched_text)

    # Split text into words and check each word against whitelist
    words = re.findall(r'\b\w+\b', text)
    # Use unique placeholders per whitelisted token to avoid collisions between
    # different words of the same length (e.g., "тебя" vs "себя").
    placeholder_map: Dict[str, str] = {}
    for word in words:
        if _is_whitelisted_word(word):
            key = word.lower()
            if key not in placeholder_map:
                placeholder_map[key] = f"__WHITELIST_{len(word)}_{len(placeholder_map)}__"
            placeholder = placeholder_map[key]
            text = text.replace(word, placeholder)
    
    filtered_text = text
    for patterns in [_BANNED_PATTERNS, _BANNED_SUFFIX_PATTERNS, _BANNED_PREFIX_SUFFIX_PATTERNS]:
        for pat in patterns:
            filtered_text = pat.sub(repl, filtered_text)
    
    # Restore whitelisted words using the unique placeholders map
    # If the same lowercase token appears with different casing, the last
    # occurrence determines the restored casing, matching prior behavior.
    for word in words:
        if _is_whitelisted_word(word):
            key = word.lower()
            placeholder = placeholder_map.get(key)
            if placeholder:
                filtered_text = filtered_text.replace(placeholder, word)
    
    return filtered_text

# ----------------- Detoxify Helpers -----------------

_LATIN_TO_CYR = dict(zip('aceopxyhkmtlACEOPXYHKMTL', 'асеорхункмтлАСЕОРХУНКМТЛ'))

def _to_cyrillic_confusables(text: str) -> str:
    return ''.join(_LATIN_TO_CYR.get(ch, ch) for ch in text) if text else text

def _collapse_spaced_letters(text: str) -> str:
    return re.sub(r"(?<=\w)\s+(?=\w)", "", text) if text else text

def _soft_tokenize(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text) if text else text

def _normalized_variants_for_ai(text: str) -> List[str]:
    if not text: return [""]
    original = _normalize_uzbek_apostrophes(_strip_zero_width(text))
    variants = [original, _to_cyrillic_confusables(original)]
    variants.extend([_collapse_spaced_letters(variants[1]), _soft_tokenize(variants[2])])
    return list(dict.fromkeys(variants))  # Deduplicate preserving order

def _chunks_for_ai(text: str, max_len: int = 250) -> Iterable[str]:
    if not text: yield ""; return
    if len(text) <= max_len: yield text; return
    start, n = 0, len(text)
    while start < n:
        end = min(n, start + max_len)
        space = text.rfind(' ', start, end)
        if space > start: yield text[start:space]; start = space + 1
        else: yield text[start:end]; start = end

def _strip_zero_width(text: str) -> str:
    """Remove zero-width chars that appear in obfuscations."""
    if not text: return text
    zw_pattern = re.compile(r'[\u200b-\u200d\u2060-\u2064\ufeff]')
    return zw_pattern.sub('', text)

def _normalize_uzbek_apostrophes(text: str) -> str:
    """Normalize various apostrophes used in Uzbek Latin to a single ASCII ' for robust matching."""
    if not text:
        return text
    try:
        return text.replace('’', "'").replace('ʼ', "'").replace('ʻ', "'")
    except Exception:
        return text

def _looks_arabic_script(s: str) -> bool:
    try:
        return any(("\u0600" <= ch <= "\u06FF") or ("\u0750" <= ch <= "\u077F") or ("\u08A0" <= ch <= "\u08FF") for ch in s)
    except Exception:
        return False

def _looks_devanagari_script(s: str) -> bool:
    try:
        return any("\u0900" <= ch <= "\u097F" for ch in s)
    except Exception:
        return False

def _looks_uzbek_latin(s: str) -> bool:
    """Heuristic: detect Uzbek Latin text based on common tokens and markers.
    This is intentionally lightweight and conservative.
    """
    try:
        if not s:
            return False
        text = s
        lower = text.lower()
        # Typical Uzbek Latin tokens
        uz_tokens = {
            'salom', 'qalesiz', 'qalaysiz', 'rahmat', 'iltimos', 'siz', 'men', 'bugun', 'universitet',
            'bekor', 'yahshi', 'yaxshi', 'kecha', 'ertaga', 'do\'st', "do'koni", 'o\'qish', "o'qish"
        }
        if any(tok in lower for tok in uz_tokens):
            return True
        # Apostrophes common in Uzbek Latin and affricates
        if any(ch in text for ch in ["'", '’', 'ʼ', 'ʻ']):
            return True
        # Character sequence markers
        if any(seq in lower for seq in [' sh', ' ch', 'ng ', ' o\'', " o'", ' g\'', " g'", ' o‘', ' g‘']):
            return True
        return False
    except Exception:
        return False

def _lang_adjusted_threshold(text: str) -> float:
    """Return toxicity threshold adjusted by detected language.
    For ar/hi/uz/kk/ky we apply stricter moderation (lower threshold).
    """
    base = float(AI_PROFANITY_THRESHOLD)
    strict_langs = {"ar", "hi", "uz", "kk", "ky", "tg"}
    lang = None
    try:
        import langid  # type: ignore
        if text and len(text) >= 3:
            lang, _ = langid.classify(text)
    except Exception:
        lang = None
    # Script-based fallback if langid is uncertain
    if not lang:
        if _looks_arabic_script(text):
            lang = "ar"
        elif _looks_devanagari_script(text):
            lang = "hi"
        else:
            # Heuristics for Tajik/Kyrgyz/Kazakh Cyrillic-specific letters
            try:
                s = text or ""
                if any(ch in set('ҳҲӣӢӯӮғҒқҚҷҶ') for ch in s):
                    lang = "tg"
                elif any(ch in set('өӨүҮңҢ') for ch in s):
                    lang = "ky"
                elif any(ch in set('әӘғҒқҚңҢұҰүҮһҺіІ') for ch in s):
                    lang = "kk"
            except Exception:
                pass
    # Treat Uzbek Latin as strict as well based on heuristics
    if (lang in strict_langs) or _looks_uzbek_latin(text):
        # Stricter moderation: allow AI to trigger at lower score
        return max(0.55, min(base, 0.6))
    # Default: conservative AI-only trigger, don't fire below 0.85 unless user configured higher
    return max(0.85, base)

def _cleanup_detoxify_cache():
    try:
        import torch
        hub_root = torch.hub.get_dir()
        candidates = []
        # Common checkpoints location
        checkpoints = os.path.join(hub_root, 'checkpoints')
        if os.path.isdir(checkpoints):
            for name in os.listdir(checkpoints):
                lower = name.lower()
                if any(k in lower for k in ("detox", "toxicity", "multilingual", "unbiased")) and name.endswith(('.pth', '.pt', '.bin')):
                    candidates.append(os.path.join(checkpoints, name))
        # Also try default cache path
        default_cache = os.path.join(os.path.expanduser('~'), '.cache', 'torch', 'hub', 'checkpoints')
        if os.path.isdir(default_cache):
            for name in os.listdir(default_cache):
                lower = name.lower()
                if any(k in lower for k in ("detox", "toxicity", "multilingual", "unbiased")) and name.endswith(('.pth', '.pt', '.bin')):
                    path = os.path.join(default_cache, name)
                    if path not in candidates:
                        candidates.append(path)
        for path in candidates:
            try:
                os.remove(path)
            except Exception:
                pass
    except Exception:
        pass

# Алиасы для совместимости с тестами
def detect_ads(text: str) -> tuple[bool, float]:
    """Detect if text contains ads. Returns (is_ad, confidence_score)"""
    if not text:
        return False, 0.0
    
    is_ad = contains_ad_words(text)
    # Простая оценка уверенности на основе количества индикаторов
    score = 0.0
    if is_ad:
        text_lower = text.lower()
        # Подсчитываем различные индикаторы рекламы
        url_matches = sum(1 for rx in _AD_REGEXES if rx.search(text_lower))
        domain_matches = sum(1 for rx in _DOMAIN_REGEXES if rx.search(text))
        word_matches = sum(1 for word in AD_RELATED_WORDS if word in text_lower)
        
        total_indicators = url_matches + domain_matches + word_matches
        score = min(1.0, total_indicators * 0.3)
    
    return is_ad, score

def calculate_spam_score(text: str) -> float:
    """Calculate spam score for text. Alias for spam_score function."""
    return spam_score(text)
