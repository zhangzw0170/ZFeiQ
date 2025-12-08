<!-- Copilot instructions for the ZFeiQ codebase (concise) -->
# ZFeiQ — AI 编码代理速查指南（精简版）

本指南提炼让代理“立即高效”所需的核心上下文：项目结构、运行入口、关键约定、常见改动路径与验证方式。仅覆盖本仓库已落地的实践与约束。

## 运行模式与入口
- 模式：`GUI`、`CLI`、`TUI`（Textual）。
- GUI/CLI（推荐在 `ZFeiQ_Original/` 目录下运行）：
  - GUI：`cd ZFeiQ_Original && python main.py`（需 `PyQt5==5.15.0`）。
  - CLI：`cd ZFeiQ_Original && python main.py --cli`。
- TUI：`cd ZFeiQ_Original && python -m zfeiq_tui.run`。
- 端口与绑定：默认 `2425`；可用 `--port <n>` 或 `ZFEIQ_PORT`；绑定网卡 `--bind <ip>`（未显式绑定时 CLI 可能自动重绑）。
- 嵌入式渲染：RK3566/aarch64 可设 `ZFEIQ_FORCE_SOFTGL=1` 以强制软件 OpenGL。

## 架构总览（核心边界与数据流）
- `zfeiq_cli/`：协议/传输/状态与无 UI 逻辑（自动化/测试首选）。
  - `protocol.py`：IPMSG 常量、报文编解码、附件编码。
  - `transport.py`：`UdpTransport` 广播/单播；Linux 监听 `0.0.0.0`，Windows 通常绑定指定接口；出站接口由 `iface_ip/iface_prefix` 推断。
  - `cli.py`：`ZFeiQCli` 生命周期、注册表、keepalive/purge、自动重绑 `_auto_rebind_consider`、加密/文件传输钩子。
  - `crypto.py`：RSA‑3072 OAEP、HKDF‑SHA256、AES‑256‑GCM（Level‑B ENC2）。
  - `filetransfer.py`：基于 TCP 的附件传输（默认端口 2425），映射存于 `_attach_map`。
  - `state.py`：内存注册与持久化辅助。
- `zfeiq_gui/`：PyQt5 UI 与后端桥接（`app.py`、`backend.py`、`pages/`、`lang.py`）。
- `zfeiq_tui/`：Textual 键盘优先界面（`run.py`，快捷键见其 README）。

## 关键运行特性与坑位
- Linux 监听 `0.0.0.0` 以可靠接收广播；出站网卡自动选路，若未锁定 `--bind` 可能被动切换。
- 解码容错链：`utf-8` → `gbk` → `cp936` → `latin-1`（`_decode_bytes_auto`）。
- 密钥位置：首次使用懒生成；在 `ZFeiQ_Original/` 版本中通常映射到 `commons/keys/`；避免日志输出私钥内容。
- 文件传输：发送端临时开放 TCP 服务供对端拉取；确保端口与 `_attach_map` 一致。

## 开发者工作流（验证优先）
- 依赖安装：`pip install -r requirements.txt`；GUI 另装 `pip install "PyQt5==5.15.0"`。
- 加密栈版本：在目标设备（如 RK3566）上确保 `pip install --upgrade "cryptography>=46.0.0"`。
- 集成演示：`python tests/discover_and_sendall.py`、`python tests/group_send_demo.py`。
- 加密冒烟：`python tests/test_key_exchange_smoke.py`（KX1/KX2/ENC2）。
- 文件回环：`python tests/test_ipmsg_getfiledata_loopback.py`、`python tests/test_intraapp_download.py`。
- 一致性检查：`python tests/parity_tests.py`、`python tests/quick_check.py`。

## 项目约定与常见改动
- 端口/编码默认值为测试前提（`2425` 与上述解码链）—非必要勿改。
- UI 文案集中于 `zfeiq_gui/lang.py`，新增/变更需同步 `backend.py`/页面组件。
- 跨平台绑定差异敏感：修改 `transport.py` 后需在 Linux/Windows 双端验证广播/单播。

## 示例性修改路径（落地步骤）
- 新 IPMSG 命令：
  1) `zfeiq_cli/protocol.py` 增常量与编/解码；
  2) `zfeiq_cli/cli.py` 按 `base_command` 添处理分支；
  3) 若需展示，补 `zfeiq_gui/backend.py` 与相关页面。
- 调整传输层：修改 `zfeiq_cli/transport.py`，再用 `tests/discover_and_sendall.py` 验证广播/群发。
- 文件传输：参考 `filetransfer.py` 与回环测试脚本，校验 `_attach_map` 与 TCP 端口一致性。

## 调试定位（入口地图）
- 启动/参数：`ZFeiQ_Original/main.py`。
- 生命周期/重绑/保活：`zfeiq_cli/cli.py`。
- 套接字与收发：`zfeiq_cli/transport.py`。
- UI 启动/桥接：`zfeiq_gui/app.py`、`zfeiq_gui/backend.py`。
- 翻译/文案：`zfeiq_gui/lang.py`。

如需扩展章节（如：新增 GUI 页面流程、TUI 交互挂钩、或 OCR/NPU 集成落地步骤），请指出具体主题以便补充示例与操作清单。
