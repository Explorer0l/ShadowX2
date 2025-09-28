import os
import sys
import asyncio

# Ensure UTF-8 console on Windows and add project root to sys.path for direct runs
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    except Exception:
        pass

# Ensure project root is importable even when executed from tests/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure AI and translation-assisted path are enabled before imports
os.environ.setdefault("AI_PROFANITY_ENABLED", "1")
os.environ.setdefault("AI_BACKEND", "ensemble")
os.environ.setdefault("AI_PROFANITY_THRESHOLD", "0.7")
os.environ.setdefault("AI_PROFANITY_TRANSLATE_AUX", "1")

from utils.filters import ai_profanity_score_async, ai_profanity_score, contains_banned_words_async, contains_banned_words, _lang_adjusted_threshold  # type: ignore
from utils.translate import detect_language, translate_to_en  # type: ignore


CASES = [
    # Kyrgyz (ky)
    ("ky", "Сен акмаксың!"),  # You're a fool!
    ("ky", "Эй, жогол!"),
    # Uzbek Latin (uz)
    ("uz", "Seni sikaman"),  # obscene
    ("uz", "Sen ahmoq ekansan"),
    # Uzbek Cyrillic (uz)
    ("uz", "Сен аҳмоқ экансан"),
    # Kazakh (kk)
    ("kk", "Сен ақымақсың"),
    ("kk", "Жоғал!"),
    # Tajik (tg)
    ("tg", "Ту аблаҳӣ!"),
    ("tg", "Ту нодон ҳастӣ"),
]


async def run_case(tag: str, text: str):
    try:
        det = await detect_language(text)
        thr = _lang_adjusted_threshold(text)
        score_async = await ai_profanity_score_async(text)
        contains_async = await contains_banned_words_async(text)
        # Try translation to show aux path effect
        translated, provider = await translate_to_en(text, detected_lang=det)
        # Also sync score for comparison
        score_sync = ai_profanity_score(text)
        print(f"[{tag}] '{text}'")
        print(f"  detected_lang={det} threshold={thr:.2f}")
        print(f"  ai_score_async={score_async:.3f} ai_score_sync={score_sync:.3f} contains_async={contains_async}")
        if translated and translated.strip() and translated.strip().lower() != text.strip().lower():
            print(f"  translated({provider}) -> '{translated}'")
    except Exception as e:
        print(f"[{tag}] '{text}' ERROR: {e}")


async def main():
    print("=== Multilingual async profanity check (ky/uz/kk/tg) ===")
    for tag, text in CASES:
        await run_case(tag, text)


if __name__ == "__main__":
    asyncio.run(main())


