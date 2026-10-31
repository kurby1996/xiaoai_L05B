import unittest
from unittest.mock import AsyncMock, patch

from xiaogpt.miot_retry import cooldown_seconds, device_command


LIMIT = Exception('Error action: {"code":-127,"message":"client withdraw","result":{"wait_second":30}}')


class DeviceCooldownTests(unittest.IsolatedAsyncioTestCase):
    async def test_obeys_server_delay_and_retries_once(self):
        with (
            patch("xiaogpt.miot_retry.miio_command", new_callable=AsyncMock, side_effect=[LIMIT, "ok"]) as send,
            patch("xiaogpt.miot_retry.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            self.assertEqual(await device_command(None, "test", "5-3 hello"), "ok")
            sleep.assert_awaited_once_with(30)
            self.assertEqual(send.await_count, 2)

    async def test_repeated_rejection_is_not_retried_forever(self):
        with (
            patch("xiaogpt.miot_retry.miio_command", new_callable=AsyncMock, side_effect=LIMIT) as send,
            patch("xiaogpt.miot_retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            with self.assertRaises(Exception):
                await device_command(None, "test", "5-3 hello")
            self.assertEqual(send.await_count, 2)

    async def test_unrelated_error_is_not_retried(self):
        with (
            patch("xiaogpt.miot_retry.miio_command", new_callable=AsyncMock, side_effect=Exception("offline")) as send,
            patch("xiaogpt.miot_retry.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            with self.assertRaisesRegex(Exception, "offline"):
                await device_command(None, "test", "5-3 hello")
            send.assert_awaited_once()
            sleep.assert_not_awaited()

    def test_invalid_cooldowns_are_ignored(self):
        for wait in (-1, 0, 301, "NaN", True, None):
            self.assertIsNone(cooldown_seconds(Exception('{"code":-127,"result":{"wait_second":' + __import__("json").dumps(wait) + '}}')))
