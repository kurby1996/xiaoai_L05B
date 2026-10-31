"""Honor Xiaomi's explicit cooldown for rejected device actions."""
import asyncio
import json

from miservice import miio_command


def cooldown_seconds(error: Exception) -> float | None:
    message = str(error)
    start = message.find('{"code"')
    if start < 0:
        return None
    try:
        response, _ = json.JSONDecoder().raw_decode(message[start:])
        wait = response.get("result", {}).get("wait_second")
        if response.get("code") != -127 or isinstance(wait, bool):
            return None
        wait = float(wait)
        return wait if 0 < wait <= 300 else None
    except (ValueError, TypeError, AttributeError):
        return None


async def device_command(service, did, command):
    try:
        return await miio_command(service, did, command)
    except Exception as error:
        wait = cooldown_seconds(error)
        if wait is None:
            raise
        print(f"小米设备接口要求等待 {wait:g} 秒，等待后重试一次。")
        await asyncio.sleep(wait)
        return await miio_command(service, did, command)
