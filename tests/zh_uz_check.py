import asyncio
from utils.translate import detect_language, translate_to_en

SAMPLES = [
    "你好，你今天怎么样？",
    "你今天好嗎？",
    "Salom, qalesiz?",
    "Salom, qalaysiz?",
    "Мен бугун университетга бораман.",
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
