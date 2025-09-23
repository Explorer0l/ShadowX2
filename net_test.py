import os, asyncio, ssl, certifi, socket, aiohttp

async def main():
    proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy")
    print("Using proxy:", proxy)

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_ctx, family=socket.AF_INET)
    timeout = aiohttp.ClientTimeout(total=25)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
        async with s.get("https://api.telegram.org/", proxy=proxy) as r:
            print("Status:", r.status)
            print("Server:", r.headers.get("server"))

if __name__ == "__main__":
    asyncio.run(main())