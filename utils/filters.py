"""
Filters module for ShadowX Bot
Contains text filtering functions for profanity and ad detection
"""

import re, os, asyncio, logging
from typing import Iterable, List
from config import (
    AI_PROFANITY_ENABLED, AI_PROFANITY_MODEL, AI_PROFANITY_BACKEND,
    AI_LANG_ROUTING, AI_PROFANITY_THRESHOLD, AI_PROFANITY_DETECTION_ONLY
)

# Safe defaults for optional config
try:
    from config import SPAM_ENABLED, SPAM_SCORE_THRESHOLD
except ImportError:
    SPAM_ENABLED, SPAM_SCORE_THRESHOLD = True, 0.6

# Optimize transformers environment
for key, val in [("TRANSFORMERS_NO_TF", "1"), ("TRANSFORMERS_NO_FLAX", "1"), 
                 ("TRANSFORMERS_NO_TORCHVISION", "1"), ("AI_DISABLE_HF", "1")]:
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
    # UZ (Latin) — minimal obscene stems
    "sik", "siki", "sikish", "sikaman", "sikdim", "sikdi",
    # RU/TJ common
    "kun","кун", "кунте", "kunte", "kunut", "kusut", "керм", "sex", "петка", "гой", "трахну", "трахать", "traxat", "trahat", "goy", "goydan", "petka",
    "охует", "охуеть", "ахуеть", "ахует", "guh", "гух", "gh", "гх", "гӯҳ", "гҳ", "дерьмо", "говно", "сучка",
    # Рус. глагол с непристойной коннотацией (основные формы)
    "сосать", "сосу", "сосал", "сосала", "сосало", "сосали", "сосешь", "сосёшь", "сосет", "сосёт",
    "сосем", "сосём", "сосете", "сосёте", "сосут", "соси", "сосите",
    # Частые базовые формы, которые могли отсутствовать
    "пизда", "пидор", "пидорас", "пидорасы", "ебать", "ебаться"
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

# Allow suffixes after obscene stems (to catch plural/cases: "пизда", "пидоразы", etc.)
_SUFFIX_STEMS = [
    "пизд", "пидор", "пидарас", "ебан", "ебат", "еба", "ёба", "трах", "шлюх",
    # To catch forms like "охуели", "охуенно", "ахуенно", "охуел"
    "охуе", "ахуе", "хуе", "хуй",
    # EN/UZ stems
    "fuck", "shit", "bitch", "sik",
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
    "ребенок", "ребенка", "ребенку", "ребенком", "ребенке", "ребята", "ребят", "ребятам"
]

_BANNED_PREFIX_SUFFIX_PATTERNS = [_build_prefix_suffix_pattern(s) for s in _PREFIX_SENSITIVE_STEMS]

def _is_whitelisted_word(word: str) -> bool:
    """Check if a word is in the whitelist and should not be filtered."""
    word_lower = word.lower().strip()
    return word_lower in _WHITELIST_WORDS

# ---- AI Profanity (optional) ----
_ai_available = False
_hf_tokenizer = None
_hf_model = None
_detoxify_available = False
_detoxify_model = None
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
    global _ai_available, _hf_tokenizer, _hf_model, _detoxify_available, _detoxify_model, _langid_available, _langid_fn, _device, _device_logged
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
            # Restrict HF scoring to Slavic/Cyrillic languages to reduce false positives
            allowed_langs = {"ru", "uk", "be", "kk", "tg", "tj", "uz", "tt"}
            lang_ok = (lang is None) or (lang in allowed_langs)
            if lang_ok:
                for variant in _normalized_variants_for_ai(text):
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
                    # Focus on explicit profanity/insults only; ignore generic 'toxic' to avoid overblocking
                    # Include 'obscenity' to match RU model label names
                    preferred_labels = ("obscene", "obscenity", "insult", "swear", "profan")
                    var_best = 0.0
                    for label, p in label_probs.items():
                        if any(label_key in label for label_key in preferred_labels):
                            var_best = max(var_best, p)
                    # Do NOT fall back to max of all labels if none matched
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

def ai_profanity_score(text: str) -> float:
    """Synchronous wrapper for backward compatibility."""
    return _ai_profanity_score_sync(text)

def ai_contains_profanity(text: str) -> bool:
    return ai_profanity_score(text) >= float(AI_PROFANITY_THRESHOLD)

async def ai_contains_profanity_async(text: str) -> bool:
    score = await ai_profanity_score_async(text)
    return score >= float(AI_PROFANITY_THRESHOLD)

def contains_banned_words(text):
    """Check if text contains banned words (robust against separators/leet/confusables)."""
    if not text:
        return False
    # If AI-only mode for detection, skip manual lists
    if AI_PROFANITY_ENABLED and AI_PROFANITY_DETECTION_ONLY:
        return ai_contains_profanity(text)
    
    # Check if any words in the text are whitelisted
    words = re.findall(r'\b\w+\b', text.lower())
    for word in words:
        if _is_whitelisted_word(word):
            # If we find whitelisted words, create a version without them for checking
            temp_text = text
            for whitelist_word in _WHITELIST_WORDS:
                if whitelist_word.lower() in temp_text.lower():
                    # Replace whitelisted word with placeholder
                    temp_text = re.sub(r'\b' + re.escape(whitelist_word) + r'\b', 
                                     '__SAFE__', temp_text, flags=re.IGNORECASE)
            
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
    for word in BANNED_WORDS:
        if word in text_lower:
            # Verify with pattern for accuracy
            for pat in _BANNED_PATTERNS:
                if pat.search(text):
                    return True
            break
    
    # Full pattern matching if no quick hits
    for pat in _BANNED_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    for pat in _BANNED_PREFIX_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    
    # AI layer (optional, conservative: only if strong AI hit)
    if AI_PROFANITY_ENABLED:
        try:
            if ai_profanity_score(text) >= max(0.85, float(AI_PROFANITY_THRESHOLD)):
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
    for word in BANNED_WORDS:
        if word in text_lower:
            for pat in _BANNED_PATTERNS:
                if pat.search(text):
                    return True
            break
    
    for pat in _BANNED_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    for pat in _BANNED_PREFIX_SUFFIX_PATTERNS:
        if pat.search(text):
            return True
    
    # AI layer (async to avoid blocking)
    if AI_PROFANITY_ENABLED:
        try:
            score = await ai_profanity_score_async(text)
            if score >= max(0.85, float(AI_PROFANITY_THRESHOLD)):
                return True
        except Exception:
            pass
    return False

def contains_ad_words(text):
    """Check if text contains advertising-related words"""
    if not text: return False
    text_lower = text.lower()
    return (any(rx.search(text_lower) for rx in _AD_REGEXES) or
            any(rx.search(text) for rx in _DOMAIN_REGEXES) or
            any(word in text_lower for word in AD_RELATED_WORDS))


def spam_score(text: str) -> float:
    """Return spam score (0..1) using lightweight heuristics."""
    if not text: return 0.0
    t = text.strip()
    score = 0.0
    
    # Count various spam indicators
    counts = {k: len(v.findall(t)) for k, v in _REGEXES.items() if k in ['url', 'handle', 'phone']}
    domain_hits = sum(len(rx.findall(t)) for rx in _DOMAIN_REGEXES)
    ad_hits = sum(1 for rx in _AD_REGEXES if rx.search(t))
    
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
    
    return max(0.0, min(1.0, score))

def contains_spam(text: str) -> bool:
    if not SPAM_ENABLED:
        return False
    return spam_score(text) >= float(SPAM_SCORE_THRESHOLD)

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
    for word in words:
        if _is_whitelisted_word(word):
            # Skip filtering for whitelisted words by temporarily replacing them
            placeholder = f"__WHITELIST_{len(word)}__"
            text = text.replace(word, placeholder)
    
    filtered_text = text
    for patterns in [_BANNED_PATTERNS, _BANNED_SUFFIX_PATTERNS, _BANNED_PREFIX_SUFFIX_PATTERNS]:
        for pat in patterns:
            filtered_text = pat.sub(repl, filtered_text)
    
    # Restore whitelisted words
    for word in words:
        if _is_whitelisted_word(word):
            placeholder = f"__WHITELIST_{len(word)}__"
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
    original = _strip_zero_width(text)
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
