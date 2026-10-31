# 小爱音箱 L05B 接入大模型

基于 [yihong0618/xiaogpt](https://github.com/yihong0618/xiaogpt) 的 Windows 本地部署，支持 DeepSeek 官方及硅基流动的 OpenAI 兼容接口。

## 已验证的功能

- 小米账号登录、短信验证码验证、选择小爱音箱 Play（L05B）。
- 读取音箱语音提问，将问题发送给配置的大模型。
- 使用 `use_command: true` 调用音箱原生语音播报，无需刷机。
- 修复本机遇到的 `-127 / client withdraw`：设备请求使用与登录相同的客户端标识。修改后实机播报成功，用户确认听到测试语音。
- 遇到带 `wait_second` 的 `-127` 响应，按服务器要求等待，最多重试一次。

2026-10-31 验证：15 项离线测试通过。仅验证了本次使用的 L05B 和账号环境，不保证所有型号或固件兼容。当前未启用联网搜索，天气等实时信息请使用小爱原生能力。

## 安装

安装 Python 3.12（上游要求 >=3.12、<3.15）和 Git，然后在 PowerShell 中执行：

```powershell
git clone https://github.com/kurby1996/xiaoai_L05B.git
cd xiaoai_L05B
python -m venv xiaogpt/.venv
./xiaogpt/.venv/Scripts/python.exe -m pip install -e ./xiaogpt
```

## 使用

按顺序双击仓库根目录中的脚本：

1. **1-配置账号和模型.cmd**：输入绑定音箱的小米账号和密码；选择 DeepSeek 官方或硅基流动，填写对应平台的 API Key 和模型名。DeepSeek 的地址和模型已有预设，回车保留。
2. **2-登录并选择音箱.cmd**：按提示输入短信验证码（不是手机号），再选择列表中的 L05B 序号。
3. **3-启动小爱AI.cmd**：保持窗口运行，唤醒“小爱同学”后，以“请”或“帮我”开头提问，例如“请讲一个简短的笑话”。Ctrl+C 停止。

首次配置会从 `config.local.example.json` 生成本机的 `config.local.json`。`--use_command` 已由启动脚本自动传入，不需要对音箱说，也不需要手动输入。

电脑和程序需要持续运行。小米云端轮询可能有延迟，也可能先听到部分原生回答。默认使用单轮、非流式回答，不保证免唤醒连续对话。切换模型平台后需填写该平台自己的 Key。

## 本机敏感文件

`config.local.json` 明文保存本机填写的账号、密码和模型 Key，`state/.mi.token` 保存小米登录凭证。两者均被 Git 忽略；不要上传、分享或粘贴到 Issue。仓库只包含空凭证示例。

## 源码与修改

`xiaogpt/` 是上游提交 [`4258b0b`](https://github.com/yihong0618/xiaogpt/commit/4258b0b53cf6af062f1a01af993d47a161382a0f) 的源码快照及本地修改，保留上游 MIT 许可证及原作者署名。它是普通源码目录，不是 Git 子模块，无需另行拉取。

主要修改：`xiaogpt/miio_compat.py` 统一设备请求客户端标识；`xiaogpt/miot_retry.py` 处理明确的服务端冷却；主程序和 MiTTS 使用兼容类；command 模式取消额外的等待提示播报。根目录的 `manage_xiaogpt.py` 提供配置、设备选择和启动入口。

本仓库将源码快照的包版本固定为 `3.24.dev5+l05b`，安装不依赖上游 Git 标签。

测试（从仓库根目录运行）：

```powershell
cd xiaogpt
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

`check_speaker.py` 会使用本机配置发送一句真实测试语音；仅在需要实机排查时手动运行。
