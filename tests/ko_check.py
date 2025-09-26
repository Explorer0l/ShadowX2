import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.translate import detect_language, translate_to_en


async def main():
    s = "모든 언어가 지원되는 것은 아니지만 잘 작동합니다."
    lang = await detect_language(s)
    t, p = await translate_to_en(s, detected_lang=lang)
    print('Detected:', lang)
    print('Provider:', p)
    print('Translated:', t)


if __name__ == "__main__":
    asyncio.run(main())


