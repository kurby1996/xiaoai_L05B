import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from xiaogpt.config import Config
from xiaogpt.xiaogpt import MiGPT


class VoiceReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MiGPT(Config(openai_key="test", printer_enabled=True, mute_xiaoai=True))
        self.bot.started_timestamp = self.bot.last_timestamp = 100

    async def asyncTearDown(self):
        await self.bot.close()

    def page(self, *records):
        return {"data": json.dumps({"records": list(records)})}

    def test_all_pending_commands_are_received_in_time_order(self):
        self.bot.polling_event.clear()  # model/printer/voice is currently busy
        records = [dict(time=103, requestId="c", query="打印1234"),
                   dict(time=102, requestId="b", query="请讲笑话"),
                   dict(time=101, requestId="a", query="帮我解释一下")]
        self.bot._get_last_query(self.page(*records))
        self.assertEqual([self.bot.last_record.get_nowait()["requestId"] for _ in range(3)], ["a", "b", "c"])
        self.bot._get_last_query(self.page(*records))
        self.assertTrue(self.bot.last_record.empty())

    def test_same_timestamp_and_late_cloud_updates_do_not_get_lost(self):
        self.bot._get_last_query(self.page(dict(time=105, requestId="a", query="打印1234")))
        self.bot._get_last_query(self.page(dict(time=104, requestId="late", query="打印5678"),
                                           dict(time=105, requestId="b", query="请讲笑话")))
        self.assertEqual(self.bot.last_record.qsize(), 3)

    def test_full_queue_does_not_acknowledge_unqueued_commands(self):
        self.bot.last_record = asyncio.Queue(1)
        page = self.page(dict(time=101, requestId="a", query="打印1234"),
                         dict(time=102, requestId="b", query="打印5678"))
        self.bot._get_last_query(page)
        self.assertEqual(self.bot.last_record.get_nowait()["requestId"], "a")
        self.bot._get_last_query(page)
        self.assertEqual(self.bot.last_record.get_nowait()["requestId"], "b")

    def test_old_records_are_not_replayed_and_noncommands_do_not_fill_queue(self):
        self.bot._get_last_query(self.page(dict(time=99, requestId="old", query="打印1234"),
                                           dict(time=101, requestId="skip", query="今天天气")))
        self.assertTrue(self.bot.last_record.empty())

    async def test_poller_survives_failure_and_runs_while_consumer_is_busy(self):
        self.bot.polling_event.clear()
        self.bot.get_latest_ask_from_xiaoai = AsyncMock(side_effect=[RuntimeError("temporary"), None, asyncio.CancelledError()])
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=SimpleNamespace())
        session.__aexit__ = AsyncMock(return_value=False)
        with patch("xiaogpt.xiaogpt.ClientSession", return_value=session), patch("xiaogpt.xiaogpt.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(asyncio.CancelledError):
                await self.bot.poll_latest_ask()
        self.assertEqual(self.bot.get_latest_ask_from_xiaoai.await_count, 3)

    async def test_pause_failure_does_not_kill_request_processing(self):
        self.bot.mina_service = SimpleNamespace(player_get_status=AsyncMock(side_effect=TimeoutError()))
        await self.bot.stop_if_xiaoai_is_playing()

    async def test_empty_model_result_has_audible_feedback(self):
        self.bot.__dict__["chatbot"] = SimpleNamespace(ask=AsyncMock(return_value=""))
        answers = [text async for text in self.bot.ask_gpt("test")]
        self.assertIn("暂时没有返回", answers[0])

    async def test_stuck_playback_state_is_bounded(self):
        from xiaogpt.tts.mi import MiTTS
        tts = MiTTS(SimpleNamespace(account=None), "speaker", self.bot.config)
        tts.get_if_xiaoai_is_playing = AsyncMock(side_effect=TimeoutError())
        with patch("xiaogpt.tts.base.asyncio.sleep", new_callable=AsyncMock):
            await tts.wait_for_duration(0)
