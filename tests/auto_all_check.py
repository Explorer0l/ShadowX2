import asyncio
from utils.translate import maybe_augment_with_english

SAMPLES = [
    "你好，今天怎么样？",
    "Проверяем автоопределение и перевод",
    "Ҳоло ман як паёмро месанҷам",
    "Salom, bugun qalesiz?",
]

async def main():
    for t in SAMPLES:
        print('---')
        print('Original:', t)
        out = await maybe_augment_with_english(t)
        print(out)

if __name__ == '__main__':
    asyncio.run(main())
