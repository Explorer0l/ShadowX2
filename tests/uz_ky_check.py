import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.translate import detect_language, translate_to_en

SAMPLES = [
    # Uzbek Latin
    "Salom, qalesiz?",
    "Men bugun universitetga boraman.",
    # Uzbek Cyrillic
    "Салом, рақмат!",
    "Мен бугун университетга бораман.",
    # Kyrgyz
    "Салам, кандайсыз?",
    "Саламатсызбы, бүгүн канча саатта жолугушабыз?",
]

async def main():
    for text in SAMPLES:
        lang = await detect_language(text)
        translated, provider = await translate_to_en(text, detected_lang=lang)
        print("Original:", text)
        print("Detected:", lang)
        print("Provider:", provider)
        print("Translated:", translated)
        print()

if __name__ == "__main__":
    asyncio.run(main())
