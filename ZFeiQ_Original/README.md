
# ZFeiQ（IPMSG/飞秋互通 · CLI + GUI） — Alpha 4.0

ZFeiQ 是一个基于 Python 的局域网即时通信工具，兼容飞秋/IPMSG 协议，支持 Windows 与 Linux（含 Ubuntu Kylin aarch64 / RK3566）。

## 项目要求（禁止修改）

在瑞芯微板子麒麟系统实现简单的局域网飞秋功能。

1. 可以建立无需服务器的聊天室,具有群聊天室的功能.
2. 搜索用户功能，可通过输入用户名、组名、IP等来查找我的好友.
3. 分组功能，给所有在线的用户群发消息及分组群发功能.
4. 支持表情包发送(可自定义表情包)、截图功能。
5. 调用RK3569/3566的NPU，实现典型边缘AI智能的加速功能

## 最新特性（Alpha 4.0）

- **语言切换与文本管理完全模块化**：所有界面文本集中管理，切换语言时所有页面即时刷新。
- **所有页面命名与引用统一**：如 chat_page、userlist_page，代码结构更清晰。
- **设置页控件宽度自适应**：右侧栏缩小时内容仍能完整显示。
- **头像预览逻辑更健壮**：仅在有效路径时显示图片。
- **侧栏间距完全可调**：QSplitter 逻辑优化，体验更灵活。
- **嵌入式适配与异常保护**：RK3566/aarch64 环境自动启用软件 OpenGL，字体优先系统回退本地，关键操作多层异常保护，缺少依赖时可降级运行。
- **气泡式聊天体验**：本地消息右对齐绿色气泡，对端消息左对齐白色气泡，均显示用户名与 IP。
- **文件块统一发送**：输入框支持拖拽/粘贴/对话框选择文件，统一以“文件块”形式发送，进度与完成提示嵌入聊天区。
- **中英双语支持**：界面、设置、提示文本均支持简体中文与英文，主题可选深色/浅色。
- **加密通讯**：支持 RSA‑3072 + AES‑256‑GCM 混合加密，指纹展示，严格模式下无公钥拒绝发送。
- **配置持久化**：所有设置（语言、状态、主题、下载目录、头像等）自动保存。

## 快速开始

1. 安装依赖（建议 Python 3.8+，需 pip）：

   ```pwsh
   pip install -r requirements.txt
   pip install "PyQt5==5.15.0"
   ```

2. 启动 GUI：

   ```pwsh
   python main.py
   ```

3. 启动 CLI（命令行模式）：

   ```pwsh
   python main.py --cli
   ```

## 运行说明（重要细节）

- 默认网络端口：`2425`。可传入 `--port <num>` 或使用环境变量 `ZFEIQ_PORT` 覆盖。
- 指定绑定地址：使用 `--bind <ip>`（例如 `--bind 192.168.1.5`）来锁定本地网卡，CLI 在未显式绑定时会尝试自动选择最佳本地 IP。
- GUI 平台注意：GUI 需要 `PyQt5==5.15.0`。在嵌入式或 RK3566/aarch64 上如果出现 OpenGL 问题，可强制软件渲染：
  - PowerShell (临时)：

   ```pwsh
   $env:ZFEIQ_FORCE_SOFTGL = '1'
   python main.py
   ```

- RSA 密钥：程序会在第一次需要时自动生成密钥对并写入 `./keys/priv.pem` 与 `./keys/pub.pem`。要强制重新生成，删除 `./keys/` 下的文件后重启程序。
- 文件传输：IPMSG 附件互操作通过内置的小型 TCP 服务（默认端口 2425）实现；发送方会创建一个 TCP offer，接收方通过 offer 下载文件，相关映射存于 CLI 的 `_attach_map`。

## 开发与调试要点

- 自动重绑：在 CLI 模块 `zfeiq_cli/cli.py` 中，`_auto_rebind_consider` 会基于收到的报文自动切换到与对端同网段的本地 IP（除非通过 `--bind` 锁定）。修改网卡选择逻辑请在此处调整。
- 传输实现：`zfeiq_cli/transport.py` 封装了 `UdpTransport`，在 Windows 上通常绑定到指定网卡地址，在 Linux 上为了可靠接收广播会绑定 `0.0.0.0` 并通过 `iface_ip`/`iface_prefix` 计算发送网卡。
- 协议点：IPMSG 常量与 packet 编/解码在 `zfeiq_cli/protocol.py`，新增协议命令应在该文件添加常量与解析逻辑，并在 `cli.py` 的接收分支中处理。

## 运行示例（多端本机测试）

- 在一台机器同时运行两个 CLI 实例（不同端口）用于调试：
   ```pwsh
   # 终端 1
   python main.py --cli --port 2425

   # 终端 2
   python main.py --cli --port 2426
   ```

- 运行测试脚本（示例）:
   ```pwsh
   python tests/discover_and_sendall.py
   python tests/group_send_demo.py
   ```


## 适用场景
- 局域网即时通信、文件收发、分组群聊
- 教学演示、嵌入式板卡（RK3566/Ubuntu Kylin）

## 版权声明
本项目仅用于学习与交流，禁止用于违法场景。欢迎反馈建议。

