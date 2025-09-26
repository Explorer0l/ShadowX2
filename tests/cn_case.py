import asyncio
from utils.translate import detect_language, translate_to_en

text = """我想知道它翻譯中文的效果是否一樣糟糕？
№355"""

async def main():
    lang = await detect_language(text)
    translated, provider = await translate_to_en(text, detected_lang=lang)
    print('Detected:', lang)
    print('Provider:', provider)
    print('Translated:', translated)

if __name__ == '__main__':
    asyncio.run(main())
