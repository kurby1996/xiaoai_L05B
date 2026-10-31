"""Read-only cloud conversation check; never display speech or credentials."""
import asyncio
import json
import os
import time

from aiohttp import ClientSession, ClientTimeout
from manage_xiaogpt import TOKEN, load
from xiaogpt.config import Config, LATEST_ASK_API
from xiaogpt.xiaogpt import MiGPT


async def main():
    os.environ["XIAOGPT_MI_TOKEN_PATH"] = str(TOKEN)
    bot = MiGPT(Config(**load()))
    try:
        await bot.init_all_data()
        async with ClientSession(cookie_jar=bot.cookie_jar, timeout=ClientTimeout(total=15)) as session:
            for index in range(3):
                started = time.perf_counter()
                async with session.get(LATEST_ASK_API.format(hardware=bot.config.hardware, timestamp=int(time.time() * 1000))) as response:
                    data = await response.json()
                    payload = data.get("data") or {}
                    payload = json.loads(payload) if isinstance(payload, str) else payload
                    records = payload.get("records") or []
                    print(f"sample={index + 1} http={response.status} code={data.get('code')} records={len(records)} elapsed={time.perf_counter() - started:.2f}s")
                if index < 2:
                    await asyncio.sleep(1)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=60))
