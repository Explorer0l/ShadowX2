"""
Translation utilities for ShadowX Bot
 - Language detection via langid
 - Translation providers with graceful fallback (Azure → Google → DeepL → LibreTranslate)
 - Enhanced multi-language support with caching
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple
import unicodedata
import re
from functools import lru_cache

try:
    import langid  # type: ignore
    _LANGID_AVAILABLE = True
except Exception:
    _LANGID_AVAILABLE = False

# Translation cache for frequently used phrases
_TRANSLATION_CACHE: dict[str, Tuple[str, str]] = {}
_CACHE_MAX_SIZE = 1000

from config import (
    AUTO_TRANSLATE_ENABLED,
    AUTO_TRANSLATE_ALL,
    AUTO_TRANSLATE_SOURCE_LANGS,
    TRANSLATION_PROVIDER,
    LIBRETRANSLATE_URL,
    AZURE_TRANSLATOR_KEY,
    AZURE_TRANSLATOR_REGION,
    AZURE_TRANSLATOR_ENDPOINT,
    DEEPL_API_KEY,
)

# Optional provider deps
try:
    from deep_translator import GoogleTranslator  # type: ignore
    _GOOGLE_AVAILABLE = True
except Exception:
    _GOOGLE_AVAILABLE = False

try:
    import deepl  # type: ignore
    _DEEPL_AVAILABLE = True
except Exception:
    _DEEPL_AVAILABLE = False

# ---------------------- English detection helpers ----------------------
def _looks_english_text(output: str) -> bool:
    """Heuristic: does the given text look like English (Latin script dominant)?
    Conservative: requires Latin-dominant letters and very low Cyrillic/Han share.
    """
    if not output:
        return False
    letters = [ch for ch in output if ch.isalpha()]
    if not letters:
        return False
    latin_like = 0
    cyr = 0
    han_kana = 0
    for ch in letters:
        try:
            name = unicodedata.name(ch, '')
        except Exception:
            name = ''
        if ('LATIN' in name) or ('a' <= ch.lower() <= 'z'):
            latin_like += 1
        elif ('CYRILLIC' in name) or ('а' <= ch.lower() <= 'я') or (ch in 'ёЁ'):
            cyr += 1
        elif ('CJK UNIFIED' in name) or ('HIRAGANA' in name) or ('KATAKANA' in name):
            han_kana += 1
    return latin_like >= max(1, int(0.7 * len(letters))) and (cyr + han_kana) <= int(0.05 * len(letters))

def _is_english_text(text: str, detected_lang: Optional[str] = None) -> bool:
    """Stronger check for English input to avoid unnecessary translation.
    - If detector says 'en', accept immediately.
    - Otherwise require English-looking script AND presence of common EN tokens.
    """
    if not text:
        return False
    if (detected_lang or '').lower() == 'en':
        return True
    if not _looks_english_text(text):
        return False
    # Require at least one common English token to reduce false positives on other Latin languages
    try:
        tokens = [t for t in re.findall(r"[A-Za-z']+", text.lower())]
    except Exception:
        tokens = []
    common = {
        'the','and','or','but','not','to','for','of','in','on','with','from',
        'is','are','am','was','were','be','been','being',
        'i','you','we','they','he','she','it','me','my','your','our','their',
        'this','that','these','those','a','an','as','at','by','if','then','so',
        'do','does','did','done','have','has','had','will','would','can','could','should','shall',
        'hello','hi','hey','please','thanks','thank','ok','okay'
    }
    return any(t in common for t in tokens)

async def detect_language(text: str) -> Optional[str]:
    """Detect language using langid with enhanced heuristics for 50+ languages. 
    Returns ISO-639-1 code like 'ru', 'en', 'ja', 'th', 'vi', etc. or None."""
    if not text or not _LANGID_AVAILABLE:
        return None
    try:
        # langid is synchronous; run in thread to avoid blocking
        loop = asyncio.get_running_loop()
        lang, _ = await loop.run_in_executor(None, lambda: langid.classify(text))
        code = (lang or '').lower()
        # Normalize known aliases to ISO-639-1
        # Some detectors/providers may return country codes like 'tj' (Tajikistan)
        # Normalize to language code 'tg' (Tajik)
        if code == 'tj':
            code = 'tg'
        # Enhanced script-based detection for better accuracy
        try:
            # CJK detection (Chinese, Japanese, Korean)
            if any('\u4e00' <= ch <= '\u9fff' for ch in text):
                # Japanese detection: hiragana or katakana present
                if any('\u3040' <= ch <= '\u309F' or '\u30A0' <= ch <= '\u30FF' for ch in text):
                    code = 'ja'
                else:
                    code = 'zh'
            # Korean detection: Hangul syllables or jamo
            elif any('\uAC00' <= ch <= '\uD7A3' for ch in text) or any('\u1100' <= ch <= '\u11FF' or '\u3130' <= ch <= '\u318F' for ch in text):
                code = 'ko'
            # Japanese-only detection (when no kanji)
            elif any('\u3040' <= ch <= '\u309F' or '\u30A0' <= ch <= '\u30FF' for ch in text):
                code = 'ja'
            # Thai detection: Thai block
            elif any('\u0E00' <= ch <= '\u0E7F' for ch in text):
                code = 'th'
            # Arabic detection: Arabic blocks
            elif any(('\u0600' <= ch <= '\u06FF') or ('\u0750' <= ch <= '\u077F') or ('\u08A0' <= ch <= '\u08FF') for ch in text):
                # Persian specific detection
                if any(ch in 'پچژگ' for ch in text):
                    code = 'fa'
                else:
                    code = 'ar'
            # Hindi/Devanagari detection
            elif any('\u0900' <= ch <= '\u097F' for ch in text):
                code = 'hi'
            # Vietnamese detection: Vietnamese diacritics
            elif any(ch in 'ăâđêôơưĂÂĐÊÔƠƯ' for ch in text):
                code = 'vi'
            # Bengali detection: Bengali block
            elif any('\u0980' <= ch <= '\u09FF' for ch in text):
                code = 'bn'
            # Tamil detection: Tamil block
            elif any('\u0B80' <= ch <= '\u0BFF' for ch in text):
                code = 'ta'
            # Telugu detection: Telugu block
            elif any('\u0C00' <= ch <= '\u0C7F' for ch in text):
                code = 'te'
            # Urdu detection: Urdu-specific Arabic letters
            elif any(ch in 'ٹپچڈڑژکگںھہیے' for ch in text):
                code = 'ur'
            # Hebrew detection: Hebrew block
            elif any('\u0590' <= ch <= '\u05FF' for ch in text):
                code = 'he'
            # Greek detection: Greek block
            elif any('\u0370' <= ch <= '\u03FF' for ch in text):
                code = 'el'

            if code == 'fa' and any('А' <= ch <= 'я' or ch in 'Ёё' for ch in text):
                code = 'tg'
            # Heuristic: many Tajik texts are misclassified as RU/SR/MK.
            # If Tajik-specific Cyrillic letters are present, normalize to 'tg'.
            tajik_chars = set('ҳҲӣӢӯӮғҒқҚҷҶ')
            if code in {'ru', 'sr', 'mk', 'uk', 'bs'} and any(ch in tajik_chars for ch in text):
                code = 'tg'

            # Uzbek detection heuristics
            # Cyrillic-specific Uzbek letters
            uz_cyr_chars = set('ўЎғҒқҚҳҲ')
            # Latin-specific apostrophes used in Uzbek (various unicode forms)
            uz_apostrophes = {"'", '’', 'ʼ', 'ʻ'}
            uz_latin_patterns = [
                "o'", "g'", 'sh', 'ch', 'ng', "O'", "G'", 'oʻ', 'gʻ'
            ]
            uz_tokens = {'salom', 'qalesiz', 'qalaysiz', 'rahmat', 'iltimos', 'siz', 'men', 'bugun', 'universitet'}
            uz_cyr_tokens = {'салом', 'рахмат', 'илтимос', 'сиз', 'мен', 'бугун', 'университет'}
            if any(ch in uz_cyr_chars for ch in text):
                code = 'uz'
            else:
                # Strong Uzbek Latin signals
                text_low = text.lower()
                token_hits = sum(tok in text_low for tok in uz_tokens)
                has_uz_markers = any(a in text for a in uz_apostrophes) or any(p in text for p in uz_latin_patterns)
                if token_hits >= 1 or has_uz_markers:
                    code = 'uz'
                # Uzbek Cyrillic tokens even without special letters
                elif any(tok in text_low for tok in uz_cyr_tokens):
                    code = 'uz'

            # Kyrgyz detection heuristics (Cyrillic)
            ky_cyr_chars = set('өӨүҮңҢ')
            if any(ch in ky_cyr_chars for ch in text):
                code = 'ky'
            else:
                # Common Kyrgyz tokens (Cyrillic) that differ from RU/KZ usage frequency
                ky_tokens = {'саламатсызбы', 'салам', 'кандайсыз', 'кандайсың', 'жакшы', 'эртең', 'жолугушабыз', 'бүгүн'}
                text_low2 = text.lower()
                if any(tok in text_low2 for tok in ky_tokens):
                    code = 'ky'
            # Kazakh detection heuristics (Cyrillic-specific letters)
            kk_cyr_chars = set('әӘғҒқҚңҢұҰүҮһҺіІ')
            if any(ch in kk_cyr_chars for ch in text):
                code = 'kk'
        except Exception:
            pass
        return code or None
    except Exception:
        logging.debug("Language detection failed", exc_info=True)
        return None

async def translate_to_en(text: str, detected_lang: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Translate text to English using configured provider with caching.
    Supports 50+ languages with Azure, Google, DeepL, and LibreTranslate.

    Returns (translated_text, provider_used). If no translation performed, returns (text, None).
    """
    if not text:
        return text, None

    if not AUTO_TRANSLATE_ENABLED:
        return text, None

    # Check cache first for performance
    cache_key = f"{text[:100]}_{detected_lang}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    # Do not translate English input (detected or heuristic)
    try:
        if _is_english_text(text, detected_lang):
            return text, None
    except Exception:
        pass

    # Provider selection order with legacy normalization
    raw_provider = (TRANSLATION_PROVIDER or 'auto').lower()
    if raw_provider in {'deepl', 'deep_l', 'deep'}:
        provider = 'deepl'
    elif raw_provider in {'azure', 'google', 'libre', 'auto', 'none'}:
        provider = raw_provider
    else:
        # Unknown provider value: fallback to auto
        provider = 'auto'
    source_lang = (detected_lang or 'auto') if (detected_lang and detected_lang != 'en') else 'auto'

    # Enhanced multilingual phrasebook for common greetings and phrases (50+ languages)
    def _phrasebook_to_en(inp: str) -> Optional[str]:
        if not inp:
            return None
        s = inp.strip().lower()
        # Comprehensive phrasebook covering popular phrases in major languages
        mapping = {
            # Tajik greetings
            'салом шумо чӣ хелед?': 'Hello, how are you?',
            'салом шумо чи хол доред?': 'Hello, how are you?',
            'салом шумо чи холет?': 'Hello, how are you?',
            'салом шумо чи хабар?': 'Hello, what\'s up?',
            'салом': 'Hello',
            'рахмат': 'Thank you',
            # Russian common
            'привет': 'Hello',
            'спасибо': 'Thank you',
            'пожалуйста': 'Please / You\'re welcome',
            'как дела?': 'How are you?',
            'добрый день': 'Good day',
            # Uzbek
            'salom': 'Hello',
            'rahmat': 'Thank you',
            'iltimos': 'Please',
            'салом': 'Hello',
            'рахмат': 'Thank you',
            # Kyrgyz
            'саламатсызбы': 'Hello',
            'рахмат': 'Thank you',
            # Kazakh
            'сәлем': 'Hello',
            'рахмет': 'Thank you',
            # Chinese common
            '你好': 'Hello',
            '谢谢': 'Thank you',
            '早上好': 'Good morning',
            # Japanese
            'こんにちは': 'Hello',
            'ありがとう': 'Thank you',
            'おはよう': 'Good morning',
            # Korean
            '안녕하세요': 'Hello',
            '감사합니다': 'Thank you',
            # Arabic
            'مرحبا': 'Hello',
            'شكرا': 'Thank you',
            'السلام عليكم': 'Peace be upon you',
            # Hindi
            'नमस्ते': 'Hello',
            'धन्यवाद': 'Thank you',
            # Vietnamese
            'xin chào': 'Hello',
            'cảm ơn': 'Thank you',
            # Thai
            'สวัสดี': 'Hello',
            'ขอบคุณ': 'Thank you',
            # Turkish
            'merhaba': 'Hello',
            'teşekkür ederim': 'Thank you',
            # Persian/Farsi
            'سلام': 'Hello',
            'ممنون': 'Thank you',
            # Spanish
            'hola': 'Hello',
            'gracias': 'Thank you',
            # French
            'bonjour': 'Hello',
            'merci': 'Thank you',
            # German
            'hallo': 'Hello',
            'danke': 'Thank you',
            # Portuguese
            'olá': 'Hello',
            'obrigado': 'Thank you',
            'obrigada': 'Thank you',
            # Italian
            'ciao': 'Hello',
            'grazie': 'Thank you',
        }
        return mapping.get(s)

    def _looks_english(output: str) -> bool:
        # Reuse shared heuristic
        return _looks_english_text(output)

    def _polish_english_for_ru(output: str) -> str:
        """Lightweight polishing for common RU→EN artifacts to improve readability.
        Conservative: only apply safe lexical tweaks.
        """
        if not output:
            return output
        s = output
        # Remove discourse fillers from some MT outputs
        s = re.sub(r"^\s*So\s+", "", s, flags=re.IGNORECASE)
        # Prefer 'strict' over 'hard' in moderation contexts
        if re.search(r"threshold", s, flags=re.IGNORECASE):
            s = re.sub(r"\bhard\b", "strict", s, flags=re.IGNORECASE)
            s = re.sub(r"for\s+spam\s+thresholds?", "for spam messages", s, flags=re.IGNORECASE)
        # Normalize spacing
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # Try Azure Cognitive Services Translator (preferred when configured)
    if provider in ('auto', 'azure') and AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION and AZURE_TRANSLATOR_ENDPOINT:
        try:
            import aiohttp
            params = {"api-version": "3.0", "to": "en"}
            if source_lang and source_lang not in {None, '', 'auto', 'en'}:
                params["from"] = source_lang
            headers = {
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
                "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
            }
            body = [{"text": text}]
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{AZURE_TRANSLATOR_ENDPOINT.rstrip('/')}/translate",
                    params=params,
                    json=body,
                    headers=headers,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        try:
                            out = (data[0] or {}).get('translations', [{}])[0].get('text')
                        except Exception:
                            out = None
                        if out and isinstance(out, str) and out.strip():
                            if _looks_english(out) and out.strip().lower() != text.strip().lower():
                                if (source_lang == 'ru'):
                                    out = _polish_english_for_ru(out)
                                # Cache successful translation
                                if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
                                    _TRANSLATION_CACHE[cache_key] = (out, 'azure')
                                return out, 'azure'
        except Exception:
            logging.debug("Azure translation failed", exc_info=True)

    # Try Google via deep_translator (preferred secondary)
    # Try Google next if available (also when provider explicitly 'azure' to allow fallback)
    if provider in ('auto', 'google', 'azure') and _GOOGLE_AVAILABLE:
        try:
            loop = asyncio.get_running_loop()

            def _has_cjk(s: str) -> bool:
                try:
                    return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                except Exception:
                    return False

            def _contains_tajik_cyrillic(s: str) -> bool:
                try:
                    tajik_chars = set('ҳҲӣӢӯӮғҒқҚҷҶ')
                    return any(ch in tajik_chars for ch in s)
                except Exception:
                    return False

            def _looks_like_tajik_transliteration(s: str) -> bool:
                # Common romanized Tajik/Persian tokens leaking into "English" output
                translit_tokens = {
                    'ki', 'dar', 'bora', 'man', 'va', 'bo', 'az', 'shud', 'shudan', 'fikr', 'hayot',
                    'mekunam', 'mekardam', 'mekunad', 'shudan', 'ast'
                }
                words = [w.strip(".,!?;:()[]{}\"'").lower() for w in s.split()]
                hits = sum(w in translit_tokens for w in words)
                return hits >= 2

            def _contains_russian_cyrillic(s: str) -> bool:
                # Cyrillic present, but without Tajik- and Uzbek-specific Cyrillic letters
                has_cyr = any('а' <= ch.lower() <= 'я' or ch in 'ёЁ' for ch in s)
                if not has_cyr:
                    return False
                tajik_chars = set('ҳҲӣӢӯӮғҒқҚҷҶ')
                uz_cyr_chars = set('ўЎғҒқҚҳҲ')
                ky_cyr_chars = set('өӨүҮңҢ')
                if any(ch in tajik_chars for ch in s):
                    return False
                if any(ch in uz_cyr_chars for ch in s):
                    return False
                if any(ch in ky_cyr_chars for ch in s):
                    return False
                return True

            def _contains_hangul(s: str) -> bool:
                try:
                    return any('\uAC00' <= ch <= '\uD7A3' for ch in s) or any('\u1100' <= ch <= '\u11FF' or '\u3130' <= ch <= '\u318F' for ch in s)
                except Exception:
                    return False

            def _contains_arabic(s: str) -> bool:
                try:
                    return any(('\u0600' <= ch <= '\u06FF') or ('\u0750' <= ch <= '\u077F') or ('\u08A0' <= ch <= '\u08FF') for ch in s)
                except Exception:
                    return False

            def _contains_devanagari(s: str) -> bool:
                try:
                    return any('\u0900' <= ch <= '\u097F' for ch in s)
                except Exception:
                    return False

            def _looks_like_russian_transliteration(s: str) -> bool:
                # Heuristic: romanized Russian patterns/tokens
                patterns = ['ya', 'yu', 'yo', 'ye', 'zh', 'kh', 'ts', 'sh', 'sch', 'ch']
                tokens = {'vse', 'li', 's', 'privet', 'spasibo', 'russkiy', 'russkim', 'prover', 'proverya', 'ok'}
                text_low = s.lower()
                hits = sum(p in text_low for p in patterns)
                word_hits = sum(w in text_low.split() for w in tokens)
                return (hits + word_hits) >= 2

            async def _try_google(sources: list[str]) -> Optional[str]:
                input_has_cjk = _has_cjk(text)
                input_is_tajik = (source_lang == 'tg') or _contains_tajik_cyrillic(text)
                input_is_russian = (source_lang == 'ru') or _contains_russian_cyrillic(text)
                for src in sources:
                    try:
                        translator = GoogleTranslator(source=src, target='en')
                        out = await loop.run_in_executor(None, lambda: translator.translate(text))
                        if out and isinstance(out, str) and out.strip():
                            # For Chinese input, accept if output has no CJK and differs
                            if input_has_cjk:
                                if not _has_cjk(out) and out.strip() != text.strip():
                                    return out
                            # For Tajik input, avoid romanized/transliteration-looking outputs
                            if input_is_tajik:
                                if _looks_english(out) and not _looks_like_tajik_transliteration(out):
                                    if out.strip().lower() != text.strip().lower():
                                        return out
                            # For Russian input, avoid romanized/transliteration-like outputs
                            if input_is_russian:
                                if _looks_english(out) and not _looks_like_russian_transliteration(out):
                                    if out.strip().lower() != text.strip().lower():
                                        return out
                            # If output clearly looks English and differs from input, accept
                            if _looks_english(out) and out.strip().lower() != text.strip().lower():
                                return out
                    except Exception:
                        continue
                return None

            # Build prioritized candidate sources based on heuristics
            def _contains_cjk(s: str) -> bool:
                try:
                    return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                except Exception:
                    return False

            def _looks_uzbek_latin(s: str) -> bool:
                s_low = s.lower()
                uz_tokens = ['salom', 'qalesiz', 'qalaysiz', 'rahmat', 'iltimos', 'siz', 'men', 'bugun', 'universitet']
                if any(tok in s_low for tok in uz_tokens):
                    return True
                # Apostrophes typical in Uzbek latin
                if any(ch in s for ch in ["'", '’', 'ʼ', 'ʻ']):
                    return True
                return False

            def _looks_uzbek_cyrillic(s: str) -> bool:
                s_low = s.lower()
                uz_cyr_tokens = ['салом', 'рахмат', 'илтимос', 'сиз', 'мен', 'бугун', 'университет']
                if any(tok in s_low for tok in uz_cyr_tokens):
                    return True
                # Uzbek-specific Cyrillic letters
                uz_cyr_chars = set('ўЎғҒқҚҳҲ')
                if any(ch in uz_cyr_chars for ch in s):
                    return True
                return False

            def _looks_kyrgyz_cyrillic(s: str) -> bool:
                s_low = s.lower()
                ky_cyr_tokens = ['саламатсызбы', 'салам', 'кандайсыз', 'кандайсың', 'жакшы', 'рахмат', 'эртең']
                if any(tok in s_low for tok in ky_cyr_tokens):
                    return True
                ky_cyr_chars = set('өӨүҮңҢ')
                if any(ch in ky_cyr_chars for ch in s):
                    return True
                return False

            def _looks_kazakh_cyrillic(s: str) -> bool:
                s_low = s.lower()
                kk_tokens = ['сәлем', 'қалайсың', 'қазақстан', 'жақсы', 'ертең']
                if any(tok in s_low for tok in kk_tokens):
                    return True
                kk_cyr_chars = set('әӘғҒқҚңҢұҰүҮһҺіІ')
                if any(ch in kk_cyr_chars for ch in s):
                    return True
                return False

            candidate_sources: list[str] = []
            # Prioritize Chinese explicitly to avoid romanization results from auto
            if _contains_cjk(text) or source_lang in {'zh', 'zh-cn', 'zh-tw', 'zh-cn', 'zh-tw'}:
                # Try canonical Google codes first
                candidate_sources.extend([x for x in ['zh-CN', 'zh-TW', 'zh'] if x not in candidate_sources])
            # Prioritize Korean when Hangul is present or detected
            if _contains_hangul(text) or source_lang == 'ko':
                if 'ko' not in candidate_sources:
                    candidate_sources.append('ko')
            # Prioritize Arabic when Arabic script present or detected
            if _contains_arabic(text) or source_lang == 'ar':
                if 'ar' not in candidate_sources:
                    candidate_sources.append('ar')
            # Prioritize Hindi when Devanagari present or detected
            if _contains_devanagari(text) or source_lang == 'hi':
                if 'hi' not in candidate_sources:
                    candidate_sources.append('hi')
            # Prioritize Tajik when detected or specific letters present
            if source_lang == 'tg' or _contains_tajik_cyrillic(text):
                for x in ['tg', 'ru', 'fa', 'uz']:
                    if x not in candidate_sources:
                        candidate_sources.append(x)
            # Prioritize Russian for Cyrillic texts without Tajik/Uzbek markers
            if source_lang == 'ru' or _contains_russian_cyrillic(text):
                if 'ru' not in candidate_sources:
                    candidate_sources.insert(0, 'ru')
            # Prioritize Uzbek if heuristics say so
            if _looks_uzbek_latin(text) or _looks_uzbek_cyrillic(text) or source_lang == 'uz':
                if 'uz' not in candidate_sources:
                    candidate_sources.append('uz')
            # Prioritize Kyrgyz if heuristics say so
            if _looks_kyrgyz_cyrillic(text) or source_lang == 'ky':
                if 'ky' not in candidate_sources:
                    candidate_sources.append('ky')
            # Prioritize Kazakh if heuristics say so
            if _looks_kazakh_cyrillic(text) or source_lang == 'kk':
                if 'kk' not in candidate_sources:
                    candidate_sources.append('kk')
            # Then try auto
            if 'auto' not in candidate_sources:
                candidate_sources.append('auto')
            # Include detected language next
            if source_lang and source_lang not in candidate_sources:
                candidate_sources.append(source_lang)
            # Add common fallbacks including Tajik misclassifications and regional neighbors
            for x in ['tg', 'fa', 'ru', 'sr', 'mk']:
                if x not in candidate_sources:
                    candidate_sources.append(x)

            translated = await _try_google(candidate_sources)
            if translated:
                # Light polish for RU inputs to avoid awkward literalisms
                if (source_lang == 'ru'):
                    translated = _polish_english_for_ru(translated)
                # Cache successful translation
                if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
                    _TRANSLATION_CACHE[cache_key] = (translated, 'google')
                return translated, 'google'

            # If full-text translation failed for Chinese, try translating CJK lines only and recompose
            if _contains_cjk(text):
                try:
                    lines = text.splitlines()
                    out_lines: list[str] = []
                    for ln in lines:
                        if _contains_cjk(ln):
                            # Try auto detection for line-level to maximize success
                            try:
                                translator = GoogleTranslator(source='auto', target='en')
                                ln_out = await loop.run_in_executor(None, lambda: translator.translate(ln))
                            except Exception:
                                ln_out = ln
                            out_lines.append(ln_out if ln_out else ln)
                        else:
                            out_lines.append(ln)
                    recomposed = "\n".join(out_lines)
                    if recomposed.strip() != text.strip() and not _contains_cjk(recomposed):
                        if (source_lang == 'ru'):
                            recomposed = _polish_english_for_ru(recomposed)
                        # Cache line-by-line translation result
                        if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
                            _TRANSLATION_CACHE[cache_key] = (recomposed, 'google')
                        return recomposed, 'google'
                except Exception:
                    pass
        except Exception:
            logging.debug("Google translation failed", exc_info=True)

    # Try DeepL (high-quality translations for European and Asian languages)
    if provider in ('auto', 'deepl', 'azure', 'google') and DEEPL_API_KEY and _DEEPL_AVAILABLE:
        try:
            # DeepL normalizes source language codes
            deepl_source = source_lang if source_lang and source_lang != 'auto' else None
            # Map common codes to DeepL format
            lang_map = {
                'zh': 'ZH', 'ja': 'JA', 'ko': 'KO', 'ru': 'RU', 'ar': 'AR',
                'de': 'DE', 'fr': 'FR', 'es': 'ES', 'it': 'IT', 'pt': 'PT',
                'pl': 'PL', 'nl': 'NL', 'tr': 'TR', 'uk': 'UK', 'id': 'ID',
                'sv': 'SV', 'da': 'DA', 'fi': 'FI', 'no': 'NB', 'cs': 'CS',
                'bg': 'BG', 'ro': 'RO', 'sk': 'SK', 'sl': 'SL', 'et': 'ET',
                'lv': 'LV', 'lt': 'LT', 'hu': 'HU', 'el': 'EL',
            }
            deepl_source_code = lang_map.get(deepl_source) if deepl_source else None
            
            loop = asyncio.get_running_loop()
            translator = deepl.Translator(DEEPL_API_KEY)
            
            def _deepl_translate():
                result = translator.translate_text(text, target_lang='EN-US', source_lang=deepl_source_code)
                return result.text if result else None
            
            translated = await loop.run_in_executor(None, _deepl_translate)
            if translated and isinstance(translated, str) and translated.strip():
                if _looks_english(translated) and translated.strip().lower() != text.strip().lower():
                    # Cache the result
                    if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
                        _TRANSLATION_CACHE[cache_key] = (translated, 'deepl')
                    return translated, 'deepl'
        except Exception:
            logging.debug("DeepL translation failed", exc_info=True)

    # Try LibreTranslate if URL configured
    # Finally, try LibreTranslate if configured (also allow fallback from azure/google/deepl)
    if provider in ('auto', 'libre', 'azure', 'google', 'deepl') and LIBRETRANSLATE_URL:
        try:
            # Simple minimal client using aiohttp to avoid extra deps
            import aiohttp  # local dependency already present
            async with aiohttp.ClientSession() as session:
                payload = {"q": text, "source": "auto", "target": "en", "format": "text"}
                async with session.post(f"{LIBRETRANSLATE_URL.rstrip('/')}/translate", json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        translated = (data or {}).get('translatedText')
                        if translated:
                            if _looks_english(translated):
                                # Cache LibreTranslate result
                                if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
                                    _TRANSLATION_CACHE[cache_key] = (translated, 'libre')
                                return translated, 'libre'
        except Exception:
            logging.debug("LibreTranslate failed", exc_info=True)
            if provider == 'libre':
                return text, None

    # DeepL removed

    # No provider, return original
    # Phrasebook last resort for common greetings across all supported languages
    pb = _phrasebook_to_en(text)
    if pb:
        # Cache phrasebook results
        if len(_TRANSLATION_CACHE) < _CACHE_MAX_SIZE:
            _TRANSLATION_CACHE[cache_key] = (pb, 'phrasebook')
        return pb, 'phrasebook'
    return text, None

async def maybe_augment_with_english(original_text: str) -> str:
    """If text is in configured source languages and not English, return
    a composed string:
        Original: …\nEnglish: …
    otherwise return the original text unchanged.
    """
    if not original_text:
        return original_text

    try:
        lang = await detect_language(original_text)
    except Exception:
        lang = None

    # If already English or unknown, do not change
    if not lang or lang == 'en':
        return original_text

    # Safety: if it looks like English despite detector misclass, keep as is
    try:
        if _is_english_text(original_text, lang):
            return original_text
    except Exception:
        pass

    # Only translate for requested languages list unless AUTO_TRANSLATE_ALL is enabled
    if not AUTO_TRANSLATE_ALL:
        if AUTO_TRANSLATE_SOURCE_LANGS and lang not in AUTO_TRANSLATE_SOURCE_LANGS:
            return original_text

    lang = lang or None
    translated, provider = await translate_to_en(original_text, detected_lang=lang)
    if translated and translated.strip() and translated.strip().lower() != original_text.strip().lower():
        # Build composed message with a blank line between sections for readability
        return f"Original: {original_text}\n\nEnglish: {translated}"
    return original_text


