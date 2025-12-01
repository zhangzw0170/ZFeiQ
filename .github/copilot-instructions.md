<!-- Copilot instructions for the ZFeiQ codebase -->
# ZFeiQ — AI 编码代理速查指南

本文件为 AI 编码代理在 ZFeiQ 项目中快速高效工作的要点汇总，聚焦项目特有的架构、运行方式、约定与常见修改路径。

## 运行模式与入口
- 模式：`GUI` 与 `CLI`。
- 启动 GUI：`python main.py`（依赖 `PyQt5==5.15.0`）。
- 启动 CLI：`python main.py --cli`。
- 网络端口：默认 `2425`；可用 `--port 2426` 或环境变量 `ZFEIQ_PORT`。绑定网卡：`--bind 192.168.x.x`。

## 架构总览（核心边界与数据流）
- `main.py`：入口，选择 `CLI/GUI`，传递端口/绑定配置。
- `zfeiq_cli/`：协议、传输、状态与无头交互逻辑（测试与自动化首选）。
  - `protocol.py`：IPMSG 常量、报文构造/解析、文件附件编码。
  - `transport.py`：`UdpTransport` 广播/单播；Linux 绑定 `0.0.0.0`、Windows 绑定指定接口；出站接口通过 `iface_ip/iface_prefix` 计算。
  - `cli.py`：`ZFeiQCli` 应用态与生命周期，注册表维护，keepalive/purge 循环，自动重绑 `_auto_rebind_consider`，加密/文件传输钩子。
  - `crypto.py`：RSA/AES 及 base64 工具，用于公钥交换。
  - `filetransfer.py`：基于 TCP 的文件服务/下载与 IPMSG 互通；需要时在 2425 启小型服务器；附件映射保存在 `_attach_map`。
  - `state.py`：内存注册与持久化辅助。
- `zfeiq_gui/`：PyQt5 UI 层与后端桥接。
  - `app.py`：`launch_gui()`；字体/插件与 RK3566 软 OpenGL 处理（`ZFEIQ_FORCE_SOFTGL`）。
  - `backend.py`、`main_window.py`、`pages/`：UI 绑定与页面组件；`lang.py` 统一文案与翻译。

## 关键运行特性与坑位
- Linux 默认 UDP 绑定 `0.0.0.0` 用于广播接收；出站接口由算法推断。
- 自动重绑：若未锁定绑定（`--bind` 或 `/set bind`），`ZFeiQCli` 可能因同子网流量自动切换本地绑定（见 `cli.py::_auto_rebind_consider`）。
- 密钥位置：`./keys/priv.pem` 与 `./keys/pub.pem`；懒生成（`_ensure_keys`）。
- 文件传输：触发时会在端口 2425 开 TCP 服务；附件信息通过 IPMSG 附件编码传播。
- 解码容错：`utf-8`→`gbk`→`cp936`→`latin-1` 级联（`_decode_bytes_auto`）。
- RK3566/aarch64：在特定条件下强制软件 OpenGL，避免渲染崩溃。

## 开发者工作流（实操命令）
- 安装依赖：`pip install -r requirements.txt`（GUI 需 `PyQt5==5.15.0`）。
- 快速发现与群发：运行 `tests/discover_and_sendall.py`、`tests/group_send_demo.py` 作集成演示。
- 密钥交换冒烟：`tests/test_key_exchange_smoke.py`。
- 文件传输回环：`tests/test_ipmsg_getfiledata_loopback.py` 与 `tests/test_intraapp_download.py`。
- 并行性/一致性检查：`tests/parity_tests.py`、`tests/quick_check.py`。

## 项目特有约定与修改范式
- 端口/编码默认值很敏感：测试与 Demo 假定端口 `2425` 与上述解码顺序，非必要勿改。
- 密钥目录固定：相对路径 `./keys/`，避免在日志中输出私钥内容。
- 跨平台网络绑定：Windows 与 Linux 行为不同，变更 `transport.py` 时需双平台验证广播/单播。
- 文案集中：所有 UI 字符串在 `zfeiq_gui/lang.py`，新增/变更 UI 文案务必在此维护并对齐 `backend.py`。

## 常见改动路径（示例驱动）
- 添加新的 IPMSG 命令：
  1) 在 `zfeiq_cli/protocol.py` 增加常量与编解码；
  2) 在 `zfeiq_cli/cli.py` 根据 `base_command` 添加处理分支；
  3) 若需显示到 UI，补充 `zfeiq_gui/backend.py` 与对应 `pages/` 组件。
- 传输层行为调整：
  - 修改 `zfeiq_cli/transport.py`，保留 Linux 绑定 `0.0.0.0` 与 Windows 指定接口逻辑；用 `tests/discover_and_sendall.py` 验证广播接收与群发。
- 文件传输交互：
  - 参照 `filetransfer.py` 与 `tests/test_ipmsg_getfiledata_loopback.py`，确保附件映射 `_attach_map` 与 TCP 服务端口一致。

## 调试定位建议（文件入口）
- 启动/参数：`main.py`。
- 生命周期/重绑/保活：`zfeiq_cli/cli.py`。
- 套接字与收发：`zfeiq_cli/transport.py`。
- UI 启动/桥接：`zfeiq_gui/app.py`、`zfeiq_gui/backend.py`。
- 翻译/文案：`zfeiq_gui/lang.py`。

## 最佳实践（项目内的实际偏好）
- 保持跨平台网络语义与默认端口不变。
- 变更协议/编码时先以 `tests/` 下示例脚本做集成验证。
- 变更 UI 文案集中到 `lang.py`，避免分散。

若以上任意部分仍不清晰（如：新增 GUI 页面流程、NPU/RKNN 相关 OCR 组件集成方式、或更详细的测试跑法），请告知你希望扩展的具体章节，我会补充示例与操作步骤。
