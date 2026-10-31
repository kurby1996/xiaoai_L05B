"""Send one explicit test sentence using the saved local configuration."""
import asyncio
import os
import sys

from manage_xiaogpt import ROOT, TOKEN, load
from xiaogpt.config import Config
from xiaogpt.xiaogpt import MiGPT


async def check():
    os.environ["XIAOGPT_MI_TOKEN_PATH"] = str(TOKEN)
    bot = MiGPT(Config(**load()))
    try:
        await bot.init_all_data()
        if "--mina" in sys.argv:
            result = await bot.mina_service.text_to_speech(bot.device_id, "小爱AI语音测试")
            print(f"MINA_TTS_ACCEPTED={result}")
        else:
            await bot.do_tts("小爱AI语音测试")
            print("TTS_COMMAND_ACCEPTED")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(check(), timeout=55))
