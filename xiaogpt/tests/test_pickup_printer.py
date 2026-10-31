import struct
import unittest
from unittest.mock import AsyncMock

from xiaogpt.pickup_printer import PickupPrinter, frame, parse_pickup_command, read_settings, render_ticket


class PickupCommands(unittest.IsolatedAsyncioTestCase):
    def test_codes_preserve_digits_and_separators(self):
        for query, expected in (
            ("帮我打印取件码 8888", "8888"),
            ("请打印取件码零零八八", "0088"),
            ("打印取件码８－３０２１。", "8-3021"),
            ("打印取件码幺二杠三四", "12-34"),
        ):
            self.assertEqual(parse_pickup_command(query), (True, expected))

    def test_noncommands_and_ambiguous_numbers_do_not_print(self):
        for query in ("不要打印取件码8888", "取件码8888", "怎么打印取件码", "打印机是什么"):
            self.assertEqual(parse_pickup_command(query), (False, None))
        for query in ("打印取件码", "打印取件码八千八百八十八", "打印取件码8888两份", "打印取件码8888然后关机"):
            self.assertEqual(parse_pickup_command(query), (True, None))

    async def test_same_event_prints_once_and_repeated_intent_can_print_again(self):
        printer = PickupPrinter("unused")
        printer.print_code = AsyncMock()
        await printer.handle("打印取件码8888", "event1")
        await printer.handle("打印取件码8888", "event1")
        await printer.handle("打印取件码8888", "event2")
        self.assertEqual(printer.print_code.await_count, 2)
        printer.print_code.assert_awaited_with("8888")

    async def test_uncertain_failure_is_not_retried(self):
        printer = PickupPrinter("unused")
        printer.print_code = AsyncMock(side_effect=RuntimeError("disconnected"))
        result = await printer.handle("打印取件码8888", "event1")
        await printer.handle("打印取件码8888", "event1")
        self.assertIn("不会自动重印", result)
        printer.print_code.assert_awaited_once()

    def test_ticket_has_384_dot_rows_and_protocol_checksum(self):
        image = render_ticket("0088", read_settings("missing-project"))
        self.assertEqual(image.width, 384)
        self.assertEqual(len(image.tobytes()), image.height * 48)
        packet = frame(26, struct.pack("<H", 3 * 56))
        self.assertEqual(packet[:7], bytes([2, 26, 0, 2, 0, 168, 0]))
        self.assertEqual(packet[-1], 3)
        # Golden bytes from 喵喵机上位机/protocol.js, independently checked with Node.
        self.assertEqual(frame(24, bytes(4)).hex(), "0218000400000000000f77c4ed03")
