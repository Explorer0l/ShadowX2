import asyncio
from utils.translate import detect_language, translate_to_en, maybe_augment_with_english

text = "Проверяем все ли ок с русским"

async def main():
    lang = await detect_language(text)
    translated, provider = await translate_to_en(text, detected_lang=lang)
    composed = await maybe_augment_with_english(text)
    print('Detected:', lang)
    print('Provider:', provider)
    print('Translated:', translated)
    print('Composed:')
    print(composed)

if __name__ == '__main__':
    asyncio.run(main())
