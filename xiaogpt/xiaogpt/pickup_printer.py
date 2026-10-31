"""Local pickup-code commands and Paperang P1/P1B BLE printing.

Protocol and transport follow the user's 喵喵机上位机 project. No print retries:
a failed transfer may already have produced paper.
"""
import asyncio
from collections import OrderedDict
import json
from pathlib import Path
import re
import struct
import unicodedata
import zlib

SERVICE = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
WRITES = ("49535343-8841-43f4-a8d4-ecbe34729bb3", "49535343-6daa-4d02-abf6-19569aca69fe")
NOTIFY = "49535343-1e4d-4bd9-ba61-23c647249616"
KEY = 0x35769521


def parse_pickup_command(query):
    text = unicodedata.normalize("NFKC", query).strip()
    text = re.sub(r"^(?:小爱同学[，,\s]*)?(?:(?:请|帮我)[，,\s]*)+", "", text)
    match = re.fullmatch(r"打印(?:一下|一张)?(?:快递)?取件码[是为:：，,\s]*(.*)", text)
    if not match:
        return False, None
    code = match[1].strip().rstrip("。.!！")
    code = code.translate(str.maketrans("零〇一幺二两三四五六七八九", "0011223456789"))
    code = re.sub(r"[杠横]", "-", code)
    code = re.sub(r"\s+", "", code)
    if not re.fullmatch(r"[0-9]{1,16}(?:-[0-9]{1,16}){0,3}", code) or len(code) > 32:
        return True, None
    return True, code


def frame(command, payload):
    if len(payload) > 2016:
        raise ValueError("打印协议帧过长")
    return struct.pack("<BBBH", 2, command, 0, len(payload)) + payload + struct.pack("<IB", zlib.crc32(payload, KEY) & 0xFFFFFFFF, 3)


def read_settings(project):
    settings = dict(titleFontSize=48, codeFontSize=92, padding="24", feed="3", digitSpacing=True, codeWrap=False, transferSpeed="fast")
    path = Path(project) / "config.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("version") != 2 or not isinstance(data.get("settings"), dict):
            raise ValueError("打印台配置需为版本2，请先在打印台保存设置")
        settings.update(data["settings"])
    return settings


def render_ticket(code, settings):
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path("C:/Windows/Fonts/msyhbd.ttc")
    if not font_path.exists():
        raise ValueError("未找到微软雅黑粗体字体")
    title_size = max(20, min(96, int(settings["titleFontSize"])))
    code_size = max(24, min(160, int(settings["codeFontSize"])))
    pad = max(12, min(40, int(settings["padding"])))
    display = " ".join(code) if settings["digitSpacing"] else code
    title_font = ImageFont.truetype(str(font_path), title_size)
    scratch = ImageDraw.Draw(Image.new("1", (384, 1), 1))
    font = ImageFont.truetype(str(font_path), code_size)
    if not settings["codeWrap"]:
        while scratch.textlength(display, font=font) > 344 and code_size > 12:
            code_size -= 1
            font = ImageFont.truetype(str(font_path), code_size)
    lines, current = [], ""
    for char in display:
        if current and scratch.textlength(current + char, font=font) > 344:
            lines.append(current.rstrip())
            current = ""
        current += char
    if current:
        lines.append(current.rstrip())
    title_height = int(title_size * 1.4)
    image = Image.new("1", (384, pad * 2 + title_height + len(lines) * (code_size + 12) + 12), 1)
    draw = ImageDraw.Draw(image)
    draw.text((192, pad), "取件码", font=title_font, fill=0, anchor="mt")
    for index, line in enumerate(lines):
        draw.text((192, pad + title_height + index * (code_size + 12)), line, font=font, fill=0, anchor="mt")
    return image


class PickupPrinter:
    def __init__(self, project, address="", enabled=True):
        self.project, self.address, self.enabled = project, address, enabled
        self.lock = asyncio.Lock()
        self.seen = OrderedDict()

    async def handle(self, query, event_id=None):
        recognized, code = parse_pickup_command(query)
        if not recognized:
            return None
        if not self.enabled:
            return "取件码打印功能尚未启用。"
        if not code:
            return "请说完整的取件码，例如，帮我打印取件码，八八八八。"
        if event_id is not None:
            key = str(event_id)
            if key in self.seen:
                return "这条打印指令已经处理过，不会重复打印。"
            self.seen[key] = True
            if len(self.seen) > 128:
                self.seen.popitem(last=False)
        try:
            async with self.lock:
                await asyncio.wait_for(self.print_code(code), timeout=90)
            return f"取件码{code}的打印数据已发送，请查看出纸。"
        except Exception as error:
            print(f"喵喵机打印失败：{type(error).__name__}: {error}")
            return "打印未确认完成，请检查打印机开机、有纸，并断开手机和打印台的蓝牙连接。为避免重复出纸，本次不会自动重印。"

    async def print_code(self, code):
        from bleak import BleakClient, BleakScanner
        settings = read_settings(self.project)
        feed = int(settings["feed"])
        if not 0 <= feed <= 30:
            raise ValueError("尾部走纸设置超出范围")
        image = render_ticket(code, settings)
        raster = bytes(value ^ 255 for value in image.tobytes())
        if self.address:
            device = await BleakScanner.find_device_by_address(self.address, timeout=12)
        else:
            devices = await BleakScanner.discover(timeout=8, return_adv=True)
            matches = [device for device, adv in devices.values() if "paperang" in (adv.local_name or device.name or "").lower() or SERVICE in [value.lower() for value in adv.service_uuids]]
            if len(matches) != 1:
                raise RuntimeError("未找到唯一的喵喵机，请确认开机且未被其他应用占用；多台时配置 printer_address")
            device = matches[0]
        if not device:
            raise RuntimeError("未找到配置的喵喵机")
        fast = settings["transferSpeed"] == "fast"
        async with BleakClient(device, timeout=20, winrt={"use_cached_services": False}) as client:
            characteristic = next((client.services.get_characteristic(uuid) for uuid in WRITES if client.services.get_characteristic(uuid)), None)
            if characteristic is None:
                raise RuntimeError("未找到 P1/P1B 打印通道")
            notify = client.services.get_characteristic(NOTIFY)
            if notify:
                await client.start_notify(notify, lambda *_: None)

            async def send(command, payload):
                packet = frame(command, payload)
                response = "write-without-response" not in characteristic.properties
                if response and "write" not in characteristic.properties:
                    raise RuntimeError("打印通道不可写")
                for offset in range(0, len(packet), 20):
                    await client.write_gatt_char(characteristic, packet[offset:offset + 20], response=response)
                    if not fast:
                        await asyncio.sleep(0.025)

            for command, payload in ((24, bytes(4)), (34, b"\0"), (44, b"\0")):
                await send(command, payload)
                await asyncio.sleep(0.12)
            size = 1536 if fast else 480
            for offset in range(0, len(raster), size):
                await send(0, raster[offset:offset + size])
                if not fast:
                    await asyncio.sleep(0.035)
            await send(44, b"\0")
            if feed:
                await send(26, struct.pack("<H", feed * 56))
            await send(16, b"\x01")
            await asyncio.sleep(2)
