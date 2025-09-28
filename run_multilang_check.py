import os
import asyncio

# Ensure AI/translation-assisted paths are enabled
os.environ.setdefault("AI_PROFANITY_ENABLED", "1")
os.environ.setdefault("AI_BACKEND", "ensemble")
os.environ.setdefault("AI_PROFANITY_THRESHOLD", "0.7")
os.environ.setdefault("AI_PROFANITY_TRANSLATE_AUX", "1")

from utils.filters import ai_profanity_score_async, contains_banned_words_async, _lang_adjusted_threshold  # type: ignore
from utils.translate import detect_language, translate_to_en  # type: ignore


CASES = [
    ("ky", "Сен акмаксың!"),
    ("ky", "Эй, жогол!"),
    ("uz", "Seni sikaman"),
    ("uz", "Sen ahmoq ekansan"),
    ("uz", "Сен аҳмоқ экансан"),
    ("kk", "Сен ақымақсың"),
    ("kk", "Жоғал!"),
    ("tg", "Ту аблаҳӣ!"),
    ("tg", "Ту нодон ҳастӣ"),
]


async def run_case(tag: str, text: str):
    det = await detect_language(text)
    thr = _lang_adjusted_threshold(text)
    score = await ai_profanity_score_async(text)
    flagged = await contains_banned_words_async(text)
    translated, provider = await translate_to_en(text, detected_lang=det)
    print(f"[{tag}] {text}")
    print(f"  lang={det} thr={thr:.2f} score={score:.3f} contains={flagged}")
    if translated and translated.strip() and translated.strip().lower() != text.strip().lower():
        print(f"  translated({provider}): {translated}")


async def main():
    print("=== Multilingual async profanity check (ky/uz/kk/tg) ===")
    for tag, text in CASES:
        await run_case(tag, text)


if __name__ == "__main__":
    asyncio.run(main())


