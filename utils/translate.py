"""
Translation utilities for ShadowX Bot
 - Language detection via langid
 - Translation providers with graceful fallback (Google via deep_translator, or LibreTranslate)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

try:
    import langid  # type: ignore
    _LANGID_AVAILABLE = True
except Exception:
    _LANGID_AVAILABLE = False

from config import (
    AUTO_TRANSLATE_ENABLED,
    AUTO_TRANSLATE_SOURCE_LANGS,
    TRANSLATION_PROVIDER,
    LIBRETRANSLATE_URL,
    DEEPL_API_KEY,
)

# Optional provider deps
try:
    from deep_translator import GoogleTranslator  # type: ignore
    _GOOGLE_AVAILABLE = True
except Exception:
    _GOOGLE_AVAILABLE = False

# Optional DeepL client
_DEEPL_AVAILABLE = False
try:
    if DEEPL_API_KEY:
        import aiohttp  # noqa: F401
        _DEEPL_AVAILABLE = True
except Exception:
    _DEEPL_AVAILABLE = False

async def detect_language(text: str) -> Optional[str]:
    """Detect language using langid. Returns ISO-639-1 code like 'ru', 'en', or None."""
    if not text or not _LANGID_AVAILABLE:
        return None
    try:
        # langid is synchronous; run in thread to avoid blocking
        loop = asyncio.get_running_loop()
        lang, _ = await loop.run_in_executor(None, lambda: langid.classify(text))
        return (lang or '').lower() or None
    except Exception:
        logging.debug("Language detection failed", exc_info=True)
        return None

async def translate_to_en(text: str, detected_lang: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Translate text to English using configured provider.

    Returns (translated_text, provider_used). If no translation performed, returns (text, None).
    """
    if not text:
        return text, None

    if not AUTO_TRANSLATE_ENABLED:
        return text, None

    # Provider selection order
    provider = (TRANSLATION_PROVIDER or 'auto').lower()
    source_lang = (detected_lang or 'auto') if (detected_lang and detected_lang != 'en') else 'auto'

    # Try DeepL if configured
    if provider in ('auto', 'deepl') and _DEEPL_AVAILABLE:
        try:
            import aiohttp
            params = {
                'auth_key': DEEPL_API_KEY,
                'text': text,
                'target_lang': 'EN',
            }
            if detected_lang and detected_lang != 'en':
                # DeepL expects languages like RU, ZH;
                # map iso codes when necessary
                lang_map = {'zh': 'ZH', 'ru': 'RU', 'kk': 'RU', 'tg': 'RU', 'uz': 'RU', 'ky': 'RU'}
                src = lang_map.get(detected_lang, detected_lang.upper())
                params['source_lang'] = src
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api-free.deepl.com/v2/translate', data=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tr_list = (data or {}).get('translations') or []
                        if tr_list:
                            translated = tr_list[0].get('text')
                            if translated:
                                return translated, 'deepl'
        except Exception:
            logging.debug("DeepL translation failed", exc_info=True)
            if provider == 'deepl':
                return text, None

    # Try Google via deep_translator
    if provider in ('auto', 'google') and _GOOGLE_AVAILABLE:
        try:
            loop = asyncio.get_running_loop()
            translator = GoogleTranslator(source=source_lang, target='en')
            translated = await loop.run_in_executor(None, lambda: translator.translate(text))
            if translated and isinstance(translated, str):
                return translated, 'google'
        except Exception:
            logging.debug("Google translation failed", exc_info=True)
            if provider == 'google':
                return text, None

    # Try LibreTranslate if URL configured
    if provider in ('auto', 'libre') and LIBRETRANSLATE_URL:
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
                            return translated, 'libre'
        except Exception:
            logging.debug("LibreTranslate failed", exc_info=True)
            if provider == 'libre':
                return text, None

    # No provider, return original
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

    # Only translate for requested languages list
    if AUTO_TRANSLATE_SOURCE_LANGS and lang not in AUTO_TRANSLATE_SOURCE_LANGS:
        return original_text

    lang = lang or None
    translated, provider = await translate_to_en(original_text, detected_lang=lang)
    if translated and translated.strip() and translated.strip().lower() != original_text.strip().lower():
        # Build composed message with a blank line between sections for readability
        return f"Original: {original_text}\n\nEnglish: {translated}"
    return original_text


