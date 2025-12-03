# ZFeiQ 最终技术报告（Alpha 5.2）

本报告系统性阐述 ZFeiQ 在 Alpha 5.2 版本的整体设计、关键模块、运行机理、协议与加密流程、跨平台行为、性能与可靠性策略，以及 CLI/GUI/TUI、文件传输与 OCR/NPU 集成的落地细节。目标是让读者在不阅读源码的前提下，完整理解每一条功能点“如何工作、为什么这样设计、出现问题如何定位”。

---

## 1. 项目概览与运行模式
- 形态：CLI（命令行）、GUI（PyQt5）、TUI（Textual）。
- 入口：
  - GUI：在 `ZFeiQ_Original/` 目录下执行 `python main.py`。
  - CLI：`python main.py --cli`。
  - TUI：`python -m zfeiq_tui.run`。
- 端口与绑定：默认 UDP/TCP 端口 `2425`；支持 `--port <n>` 与环境变量 `ZFEIQ_PORT`。绑定网卡通过 `--bind <ip>` 显式指定，否则 CLI 自动选路（Linux 上监听 `0.0.0.0` 以可靠接收广播，出站接口按 `iface_ip/iface_prefix` 推断）。
- 嵌入式渲染：在 RK3566/aarch64 可设 `ZFEIQ_FORCE_SOFTGL=1` 强制软件 OpenGL，避免 GPU 驱动问题影响 GUI。

设计目标：兼容 IPMSG/飞秋互通；提供轻量、稳定的局域网消息交换与附件传输，并在课程范围内集成 OCR/NPU 能力以展示边缘 AI 加速。

---

## 2. 架构分层与模块职责
- `zfeiq_cli/`：核心逻辑（协议编解码、传输、状态与加密会话、文件传输、命令处理）。
  - `protocol.py`：IPMSG 常量、命令号、帧格式、文本负载编码；KX1/KX2/ENC 前缀与字段规则。
  - `transport.py`：`UdpTransport` 对广播与单播的封装；分平台绑定策略；出站网卡推断；重试与异常保护。
  - `cli.py`：`ZFeiQCli` 生命周期；节点注册与发现；加密握手触发；消息路由；命令解析（`/set`、`/ocr`、群发等）。
  - `crypto.py`：HKDF‑SHA256 密钥派生；AES‑256‑GCM 加解密；`sid/ctr` 与 nonce/AAD 派生；重放窗口检查。
  - `filetransfer.py`：基于 TCP 的附件传输；offer 与下载映射（`_attach_map`）；默认保存目录管理。
  - `state.py`：本地配置与运行时状态持久化（路径映射到 `commons/*`）。
- `zfeiq_gui/`：PyQt5 前端，桥接后端。
  - `backend.py`：启动、登录与发现时触发广播与握手；加密状态信号；与 CLI 栈交互。
  - `app.py`、`pages/`、`lang.py`：窗口与页面；本地化；聊天头部的加密指示；控件布局。
- `zfeiq_tui/`：Textual 界面，键盘优先交互。
- `zfeiq_common/`：通用 FS 工具等。
- `tests/`：发现与群发演示、加密冒烟、文件回环等测试脚本。

分层原则：传输/协议与会话逻辑在 CLI 层统一实现，UI 仅消费事件与状态；避免在 GUI 中重复加密或网络代码，降低跨平台复杂度。

---

## 3. 协议机理（IPMSG 兼容与扩展）
### 3.1 IPMSG 基础帧
- IPMSG 消息通常通过 UDP 发送，包含命令号（如 `IPMSG_BR_ENTRY`、`IPMSG_SENDMSG` 等）以及文本负载。
- ZFeiQ 在 `protocol.py` 中定义命令常量、编解码与负载格式，兼容对端客户端的收发。
- 广播流程：上线广播；请求用户列表（GETLIST）；节点间保持心跳与去重；本机节点显示为 `LOCAL` 减少噪音。

### 3.2 自定义前缀扩展
- 握手前缀：`KX1;seedA=<b64>` 与 `KX2;seedB=<b64>`，在 `SENDMSG` 文本负载中以明文传递随机种子；双方协商派生会话密钥（见加密章节）。
- 会话消息前缀：`ENC;sid=<b64>;ctr=<u64>;tag=<b64>;payload=<b64>`；统一使用 AES‑GCM 加密的负载格式。
- 兼容：保留旧版 `ENC;...` 路径以解密对端来消息；RSA 相关路径不再用于发送，仅保留指纹展示。

设计取舍：将握手放进现有 `SENDMSG` 文本通道，避免新增复杂命令号；同时采用明文种子+HKDF 来简化椭圆曲线或 RSA 握手的跨平台依赖与复杂度。

---

## 4. 传输层机理（UDP 广播/单播与网卡选择）
- 监听策略：
  - Linux：绑定 `0.0.0.0` 以可靠接收各网段广播；出站通过计算 `iface_ip` 与 `iface_prefix` 选择最合适的本地网卡。
  - Windows：通常绑定到指定网卡地址，避免系统策略导致广播接收异常。
- 自动重绑：`cli.py` 的 `_auto_rebind_consider` 会根据接收到的报文来源动态切换出站网卡（除非 `--bind` 明确锁定）。
- 广播与单播：
  - 上线与发现：发送 `BR_ENTRY` 与能力广播（`cap=enc`、`fp=<sha256>`）。
  - 获取列表与公钥：`GETLIST` 广播、`GETPUBKEY/ANSPUBKEY` 单播或广播触发。
- 可靠性：对 UDP 的天然不可靠，通过重复广播与事件驱动重试（如发现后主动握手）提升成功率；对 ENC 消息采用重放窗口检查。

---

## 5. 加密会话机理（HKDF-only + AES‑GCM）
### 5.1 握手（KX1/KX2）
- 明文交换：发送 `KX1;seedA=<b64>` 与 `KX2;seedB=<b64>`，`seedA/seedB` 为安全随机（长度可配置）。
- IKM 构造：双方按对端与本端 IP 的字典序规则拼接 `IKM = concat(min_ip, max_ip, seedA, seedB)`，避免不同视角导致密钥不一致。
- HKDF 派生：`HKDF-SHA256` 从 `IKM` 派生 32 字节会话密钥 `K`；会话 ID `sid = SHA256(IKM)[0:8]`。
- 会话准备：初始化发送计数器 `ctr = 0` 与重放窗口；双方将对端 IP 与 `sid/K` 映射入会话表。

### 5.2 会话消息（ENC）
- 加密：`AES‑256‑GCM(K, nonce, aad=sid)` 对明文加密，输出 `cipher` 与 `tag`。
- nonce 派生：`nonce = SHA256(sid || nonce_base || ctr)[0:12]`，其中 `nonce_base` 为会话初始化随机值，`ctr` 为单调递增的 u64。
- 帧格式：`ENC;sid=<b64>;ctr=<u64>;tag=<b64>;payload=<b64>`；`aad=sid` 用于 GCM 认证。
- 重放与乱序：基于 `ctr` 的窗口检查，拒绝过旧或重复的计数器；乱序情况下允许有限窗口。

### 5.3 模式与调试
- `encrypt off|on|strict`：
  - `on`：优先使用 ENC，失败可回退（课程范围下对群聊回退到明文）。
  - `strict`：未建立会话时拒绝发送敏感消息，适合演示“加密已启用”的状态。
- CLI 辅助：
  - `/set encrypt cipher on|off`：打印原始密文用于教学。
  - `/set encrypt EDtag on|off`：在解密后的明文旁显示 `[E-D OK]` 标签。
- 事件触发：启用加密后，CLI/GUI 会主动广播能力、请求公钥并启动 `KX1/KX2`（消除仅在 debug 下成功的时序竞争问题）。

设计取舍：HKDF-only 方案极大简化跨平台握手依赖；AES‑GCM 提供认证与保密；通过 `sid/ctr` 与 SHA256 派生的 nonce 控制重放与不可预测性；strict 模式增强安全演示效果。

---

## 6. CLI/GUI/TUI 行为与交互机理
### 6.1 CLI（`zfeiq_cli/cli.py`）
- 生命周期：启动 -> 广播 -> 发现 -> 建会话（如加密启用）-> 接收与路由消息。
- 命令：
  - `/set encrypt off|on|strict`：切换模式并立即触发能力广播、公钥请求与握手。
  - `/set encrypt cipher on|off`、`/set encrypt EDtag on|off`：调试开关。
  - `/ocr <path> [--send] [--raw] [--mode auto|npu|cpu]`：调用 OCR 引擎识别文本；可直接群发结果。
  - 群发与组命令：课程范围内群聊走明文；遍历成员逐一发送。
  - 恢复指令：`purge_session <ip>` 清理会话并重试；`force_start_kx <ip>` 强制发起握手。
- 文本发送：
  - 点对点优先使用已建立的会话（ENC），否则根据模式与对端能力决定是否尝试握手或回退明文。

### 6.2 GUI（`zfeiq_gui/`）
- `backend.py`：启动/登录/发现时若加密启用，主动触发广播、公钥请求与握手；更新加密状态信号到 UI。
- `lang.py`：本地化文案，包括“通讯已加密/未加密”。
- 聊天页：聊天头部按会话状态显示加密指示；群组握手按钮默认隐藏（课程范围）。
- 体验优化：气泡聊天、文件块发送、双语主题；在嵌入式平台用软件 OpenGL 以保证可见性与性能。

### 6.3 TUI（`zfeiq_tui/`）
- Textual 应用，面向键盘操作；共享 CLI 背后逻辑；在终端友好的环境下提供轻量展示与控制。

---

## 7. 文件传输机理（TCP offer / 下载）
- 报文协商：在 IPMSG 协议中约定附件请求与应答。
- 传输流程：
  1) 发送端启动一个本地 TCP 服务（默认 2425），生成一个带附件标识的 offer 并通过 UDP 告知对端。
  2) 接收端读取 offer，连接到发送端 TCP 服务拉取文件。
- 映射与路径：
  - CLI 维护 `_attach_map` 用于跟踪附件的 offer 与下载状态。
  - 默认保存目录：若未显式指定，创建于 `commons/downloads/` 以适应嵌入式权限与路径规范。
- 可靠性与安全：限制附件大小与类型（课程演示范围）；路径与权限在 Linux 下采用安全默认值，避免跨盘符问题。

---

## 8. 状态管理与持久化
- 配置位置：统一映射到程序根目录的 `commons/*`（如 `commons/keys/`、`commons/downloads/`）。
- 键与加载：首次运行懒创建；密钥与会话状态避免泄露于日志；GUI 设置页展示真实路径。
- 会话寿命：当对端变更 IP 或失联时，清理旧会话；可通过 CLI 命令手动 `purge_session`。

---

## 9. OCR/NPU 集成机理（PP‑OCR v4 / RKNN Lite2）
- 入口：CLI `/ocr <path>`；在 RK3566 上优先 NPU 路径（RKNN Lite2），其他平台回退 CPU。
- 模型与字典：
  - RKNN：`PPOCRv4/build_output/ocr_det_rk3566_v4.rknn` 与 `ocr_rec_rk3566_v4.rknn`。
  - ONNX（CPU 备选）：`ocr_det_static.onnx` 与 `ocr_rec_static.onnx`。
  - 字典：`PPOCRv4/ppocr_keys_v1.txt`。
- 流程：
  1) 前处理：图片加载、RGB 标准化、长边缩放不超过阈值（默认 1600）。
  2) 检测：DB 模型生成文本区域 boxes，过滤低分。
  3) 识别：对每个 box 裁剪，CRNN 模型输出文本与置信度；按行与左右顺序合并。
  4) 返回：拼接文本、耗时与引擎信息（NPU/CPU）。
- 并发：初期串行；GUI 版可通过线程池异步；提供 `warmup()` 缓存上下文降低首次延迟。
- 依赖安装：RK3566 需手动安装 `rknn_toolkit_lite2`；其余依赖在 README 的 `requirements.txt` 与补充说明中提供。
- 常见提示：RKNN 的 `size_with_stride` 警告属性能建议，不影响结果；缺失模型文件时自动禁用 NPU。

---

## 10. 测试与验证
- 发现与群发：`tests/discover_and_sendall.py`、`tests/group_send_demo.py` 验证广播与群发路径。
- 加密冒烟：`tests/test_key_exchange_smoke.py`、`tests/test_handshake_enc2.py` 验证 KX1/KX2 与 ENC 收发。
- 文件传输回环：`tests/test_ipmsg_getfiledata_loopback.py`、`tests/test_intraapp_download.py` 验证 TCP offer 与下载流程。
- 一致性与快速检查：`tests/parity_tests.py`、`tests/quick_check.py`。
- OCR 集成：建议添加 `tests/test_ocr_integration.py`（报告已给出最小落地清单）。

哲学：先在特定模块做最小自测，再向更广的系统测试扩展，逐步建立信心；不要用单一脚本覆盖所有功能，避免调试复杂度过高。

---

## 11. 故障排查与运维建议
- 加密状态未显示“已加密”：确认双方版本 ≥ 5.2，网络广播与单播可达；在 CLI 执行 `/set encrypt strict` 以强制仅在会话建立后发送。
- `unknown session` 错误：握手时序竞争或丢包；可稍后自动重试或执行 `purge_session <ip>` 与 `force_start_kx <ip>`。
- GUI 空白或闪退（嵌入式）：设置 `ZFEIQ_FORCE_SOFTGL=1`；检查字体与权限降级策略。
- Windows 启动卡顿（打包）：优先“便携版”发布；如用 PyInstaller，采用 `--onedir` 并精简 hooks；若需更快启动，考虑 Nuitka 单目录构建。
- OCR 失败或耗时长：检查模型存在与依赖版本；首次调用可 `warmup()`；在超大图片时先压缩或降低长边阈值。

---

## 12. 发布与分发建议（面向 Beta 1.0）
- Windows：
  - 便携版 zip（含 venv 与依赖），启动脚本 `run_gui.bat` / `run_cli.bat`，避免 PyInstaller 单文件解包的卡顿。
  - 若必须可执行：Nuitka 单目录构建，启用 `pyqt5` 插件与包收集。
- RK3566：
  - tar.gz（含 venv、模型与 `run_gui.sh` / `run_cli.sh`），README 提示 `ZFEIQ_FORCE_SOFTGL=1` 与 RKNN Lite2 的安装方式。
- PyInstaller 使用建议：`--onedir`、明确 `--collect-data PyQt5`、`--exclude-module` 剔除未用模块；发布说明提示杀毒白名单。

---

## 13. 设计权衡与后续路线
- 简化加密：HKDF-only + ENC 统一消息，降低依赖，易于教学演示。
- 互操作优先：兼容旧 `ENC;...` 来消息，保障与外部客户端互通。
- 课程范围优化：群聊走明文、隐藏握手 UI，以稳定演示为先。
- OCR 演示充分：RK3566 上 NPU 闭环已验证；后续增强 GUI 按钮、持久化设置、CPU 路径与并发队列。
- 可选增强：用户搜索显式入口、自定义表情包的 UI 管理、延迟握手重试策略、结果结构化高亮。

---

## 14. 结语
ZFeiQ 在 Alpha 5.2 已满足课程核心要求，并以稳健的架构与简化的加密设计实现跨平台互通与可演示的边缘 AI 能力。本文档覆盖所有关键点的机理与取舍，便于后续维护、答辩与演进。