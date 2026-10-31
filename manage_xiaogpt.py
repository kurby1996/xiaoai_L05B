"""Local Windows setup and launcher for the L05B speaker."""
import asyncio
import getpass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.local.json"
TOKEN = ROOT / "state" / ".mi.token"


def load():
    if not CONFIG.exists():
        CONFIG.write_text((ROOT / "config.local.example.json").read_text(encoding="utf-8"), encoding="utf-8")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save(config):
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ask(label, previous="", secret=False):
    hint = " [已保存，回车保留]" if secret and previous else (f" [{previous}]" if previous else "")
    reader = getpass.getpass if secret else input
    return reader(label + hint + ": ").strip() or previous


def configure():
    config = load()
    print("配置仅保存在本机 config.local.json。密码和 API Key 输入时不显示。")
    config["account"] = ask("绑定音箱的小米账号", config.get("account", ""))
    config["password"] = ask("小米密码", config.get("password", ""), True)
    provider = ask("模型平台：1=DeepSeek 官方，2=硅基流动，3=保留当前/自定义", "1")
    if provider == "1":
        config["api_base"] = "https://api.deepseek.com"
        config["gpt_options"] = {"model": "deepseek-v4-flash", "extra_body": {"thinking": {"type": "disabled"}}}
    elif provider == "2":
        config["api_base"] = "https://api.siliconflow.cn/v1"
        config["gpt_options"] = {"model": ""}
        print("模型名请复制硅基流动控制台中的完整模型 ID。")
    config["api_base"] = ask("模型 API 地址（OpenAI 兼容，通常以 /v1 结尾）", config.get("api_base", ""))
    config["openai_key"] = ask("模型 API Key", config.get("openai_key", ""), True)
    config["gpt_options"]["model"] = ask("模型名称", config["gpt_options"].get("model", ""))
    save(config)
    print("配置已保存。下一步运行 2-登录并选择音箱.cmd。")


async def devices(config):
    from aiohttp import ClientSession
    from miservice import MiNAService
    from xiaogpt.xiaogpt import MiAccount

    if not config.get("account"):
        raise ValueError("请先运行 1-配置账号和模型.cmd。")
    async with ClientSession() as session:
        account = MiAccount(session, config["account"], config.get("password", ""), str(TOKEN))
        found = await MiNAService(account).device_list()
        for index, device in enumerate(found, 1):
            print(f'{index}. {device.get("name", "未命名")}  型号={device.get("hardware")}  DID={device.get("miotDID")}')
        if not found:
            raise ValueError("账号下没有找到小爱音箱，请确认绑定账号和地区。")
        choice = int(input("选择上面的 L05B 音箱序号: "))
        if not 1 <= choice <= len(found):
            raise ValueError("序号超出范围。")
        selected = found[choice - 1]
        if selected.get("hardware") != "L05B":
            raise ValueError("当前部署针对 L05B，请选择该型号。")
        if not selected.get("miotDID"):
            raise ValueError("设备没有返回 miotDID，需进一步检查设备列表。")
        config["mi_did"] = str(selected["miotDID"])
        save(config)
        print("音箱已绑定到本机配置。现在可以运行 3-启动小爱AI.cmd。")


def main():
    os.chdir(ROOT / "xiaogpt")
    TOKEN.parent.mkdir(exist_ok=True)
    os.environ["XIAOGPT_MI_TOKEN_PATH"] = str(TOKEN)
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    if mode == "configure":
        configure()
    elif mode == "devices":
        asyncio.run(devices(load()))
    elif mode == "start":
        config = load()
        missing = [key for key in ("account", "mi_did", "api_base", "openai_key") if not config.get(key)]
        if not config.get("gpt_options", {}).get("model"):
            missing.append("gpt_options.model")
        if missing:
            raise ValueError("尚未完成配置: " + ", ".join(missing) + "。请先运行步骤 1 和 2。")
        from xiaogpt.cli import main as run
        sys.argv = ["xiaogpt", "--config", str(CONFIG), "--use_command"]
        print("L05B 已启用 use_command。对音箱说：小爱同学，请介绍一下你自己。Ctrl+C 停止。")
        print("已启用小米设备接口客户端兼容修复。")
        run()
    else:
        raise ValueError("未知操作: " + mode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。")
    except Exception as error:
        print(f"操作失败: {error}")
        sys.exit(1)
