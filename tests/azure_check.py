import asyncio
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import aiohttp
from config import AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_REGION, AZURE_TRANSLATOR_ENDPOINT


async def main():
    params = {"api-version": "3.0", "to": "en"}
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
    }
    body = [{"text": "Салом, шумо чӣ ҳол доред?"}]
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{AZURE_TRANSLATOR_ENDPOINT.rstrip('/')}/translate",
            params=params,
            json=body,
            headers=headers,
            timeout=15,
        ) as resp:
            print("STATUS:", resp.status)
            txt = await resp.text()
            print("RAW:", txt)
            try:
                print("JSON:", json.loads(txt))
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())


