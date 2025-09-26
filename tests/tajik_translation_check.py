import asyncio
import os
import sys

# Allow running this script from any working directory by adding project root to sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.translate import detect_language, translate_to_en, maybe_augment_with_english


SAMPLES = [
    "Салом, шумо чӣ ҳол доред?",
    "Ман имрӯз ба донишгоҳ меравам ва ба дарс тайёр мешавам.",
    "Лутфан ин паёмро ба канал нашр кунед.",
    "Ин танҳо санҷиш аст.",
    "Мехостам як пешниҳод диҳам барои беҳтар кардани кори гурӯҳ.",
]


async def main():
    for i, text in enumerate(SAMPLES, start=1):
        lang = await detect_language(text)
        # If non-Tajik Cyrillic is detected (ru/sr/mk) but text is clearly Cyrillic Tajik,
        # override to 'tg' to evaluate end-to-end behavior for bot config.
        if lang in {"ru", "sr", "mk", "fa"} and any('А' <= ch <= 'я' or ch in 'Ёё' for ch in text):
            lang = "tg"
        translated, provider = await translate_to_en(text, detected_lang=lang)
        composed = await maybe_augment_with_english(text)
        print(f"=== Sample {i} ===")
        print(f"Original: {text}")
        print(f"Detected language: {lang}")
        print(f"Provider: {provider}")
        print(f"Translated: {translated}")
        print("Composed:")
        print(composed)
        print()


if __name__ == "__main__":
    asyncio.run(main())


