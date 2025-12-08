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

---

# Gemini 版本的最终报告

这是一个非常详尽的 FINAL_REPORT.md，基于你提供的所有源代码文件进行了深度解析。随后附带了四个视角的评价与建议。
FINAL_REPORT.md
ZFeiQ 项目最终技术报告

项目版本： Alpha 5.2 核心架构： Python (CLI Core) + PyQt5 (GUI) / Textual (TUI) 目标平台： Windows / Linux (重点适配 RK3566/Ubuntu Kylin 嵌入式环境)
1. 项目概述 (Executive Summary)

ZFeiQ 是一个基于 Python 开发的局域网即时通信系统。它不仅实现了经典的 IPMSG（飞秋/飞鸽传书）协议以保证与现有生态的互通性，还在其之上构建了一套现代化的安全层（Level B 加密），并针对瑞芯微 RK3566 边缘计算平台集成了 NPU 加速的 OCR（光学字符识别）功能。项目采用前后端分离的架构设计，核心逻辑封装在 CLI 层，支持 GUI 和 TUI 两种用户界面。
2. 系统架构设计 (System Architecture)

系统采用分层架构，确保核心逻辑的可复用性与界面的独立性。
代码段

graph TD
    User[用户] --> GUI[GUI (PyQt5)]
    User --> TUI[TUI (Textual)]
    User --> CLI_Shell[CLI 交互层]
    
    GUI --> Backend[GuiBackend (Adapter)]
    TUI --> ClientAdapter[ClientAdapter]
    
    Backend --> CLI_Core[ZFeiQCli (核心逻辑)]
    ClientAdapter --> CLI_Core
    CLI_Shell --> CLI_Core
    
    subgraph Core_Modules [核心模块]
        CLI_Core --> Transport[UDP Transport]
        CLI_Core --> Protocol[Protocol Parser/Builder]
        CLI_Core --> Crypto[Crypto Engine (HKDF/AES-GCM)]
        CLI_Core --> FileTransfer[TCP File Server/Client]
        CLI_Core --> State[State Management (Registry/History)]
        CLI_Core --> OCR[OCR Engine (RKNN/ONNX)]
    end
    
    Transport --> Network((局域网 UDP/2425))
    FileTransfer --> NetworkTCP((局域网 TCP/2425+))

2.1 核心组件解析

    zfeiq_cli (核心库): 承载所有业务逻辑，包括网络收发、协议解析、加密握手、文件传输调度。它不依赖任何 UI 库，可独立运行。

    zfeiq_gui (桌面端): 基于 PyQt5，通过 GuiBackend 将核心的事件（如收到消息）转换为 Qt 信号（Signals），实现界面异步刷新。

    zfeiq_tui (终端版): 基于 Textual 框架，专为无桌面环境或 SSH 远程连接场景设计，通过 ClientAdapter 驱动核心。

    PPOCRv4 / zfeiq_ocr: 独立的 OCR 推理模块，支持根据硬件环境自动选择 RKNN (NPU) 或 ONNX Runtime (CPU) 后端。

3. 详细运行机理 (Operating Mechanisms)
3.1 网络传输层 (transport.py)

    UDP 通信:

        绑定策略: 在 Windows 上，socket 绑定到具体网卡 IP 以避免多网卡广播冲突；在 Linux 上，绑定到 0.0.0.0 以确保能收到所有广播包，发送时通过 iface_ip 辅助判断。

        广播地址计算: 不简单使用 255.255.255.255，而是根据子网掩码（Prefix）计算定向广播地址（例如 192.168.1.255），以适应更复杂的网络拓扑。

        接收线程: 启动名为 zfeiq-recv 的守护线程，循环执行 recvfrom(65535)，收到数据后通过回调函数分发给 CLI 层。

    TCP 通信 (文件传输):

        端口复用: 默认使用 2425 端口作为文件服务端口（兼容标准 IPMSG），同时支持随机临时端口（Ephemeral Ports）用于非标准文件传输。

3.2 协议层 (protocol.py)

    报文结构: 严格遵循 IPMSG 格式 Ver:PacketNo:User:Host:Command:Extension。

        Ver: 版本号，固定为 "1"。

        PacketNo: 毫秒级时间戳 + 随机数，用于去重和 ACK 确认。

        Command: 32位整数，低8位为功能号（上线、发消息等），高24位为选项位（如 IPMSG_SENDCHECKOPT 要求回执）。

        Extension: 扩展区域，承载消息正文、文件列表或加密元数据。

    兼容性处理: 优先尝试 UTF-8 解码，失败回退到 GBK/Latin-1，完美解决与旧版“飞秋”互通时的乱码问题。

3.3 安全与加密机制 (Level B Implementation) - crypto.py & cli.py

ZFeiQ 5.2 引入了基于会话的加密方案，解决了传统 RSA 逐条加密性能低且无前向安全的问题。

    公钥交换 (IPMSG_GETPUBKEY):

        节点上线时广播携带 cap=enc 能力位。

        首次通信前，双方通过 IPMSG 扩展协议交换 RSA-3072 公钥。

        指纹验证: 计算公钥的 SHA-256 指纹，与广播报文中的指纹比对，防止简单的中间人欺骗。

    会话握手 (HKDF-only KX):

        KX1: 发起方生成 32 字节随机种子 seedA，明文发送（Level B 设计，依赖后续签名或更高层级保护，当前侧重性能与防重放）。

        KX2: 接收方生成 seedB，回复给发起方。

        密钥派生: 双方按 IP 字典序拼接 seedA 和 seedB 得到 IKM，通过 HKDF-SHA256 派生出 32 字节的会话密钥 SessionKey 和 会话ID sid。

    消息加密 (AES-GCM):

        封装: ENC;sid=...;ctr=...;tag=...;b64=...

        算法: AES-256-GCM。

        防重放: 维护一个 recv_window 滑动窗口，记录接收到的计数器 ctr。

        Nonce: 不随包传输，而是基于 SHA256(sid + ctr) 确定性派生，极大节省了带宽并防止了 Nonce 重用攻击。

3.4 文件传输机理 (filetransfer.py)

实现了两种传输模式：

    IPMSG 兼容模式:

        发送方在 UDP 报文 Extension 中附加文件元数据（以 \0 分隔）。

        接收方解析元数据，发起 TCP 连接到发送方的 2425 端口。

        发送方通过 IPMSG_GETFILEDATA 命令识别请求，发送文件流。

    内部高速模式:

        发送方创建一个临时的 SingleFileServer，监听随机端口。

        通过 UDP 发送 FILE_OFFER 专有指令，包含端口号。

        接收方直连该端口下载。这绕过了 IPMSG 协议的一些限制。

3.5 边缘 AI (OCR) 实现

    硬件感知: 启动时检测系统架构 (platform.machine()) 和依赖库。

    RKNN 路径: 若检测到 aarch64 且存在 rknn_toolkit_lite2，则加载 .rknn 模型，直接调用 NPU 进行推理。

    Fallback 路径: 若在 PC 上，自动回退到 CPU 运行（使用 ONNX 模型），确保代码“一次编写，到处运行”。

    调用流: CLI 命令 /ocr -> ZFeiQOcr 单例 -> 预处理图片 -> 推理 -> 后处理文字坐标 -> 输出结果。

3.6 GUI 实现细节 (zfeiq_gui)

    前后端解耦: GuiBackend 类继承自 QObject，它劫持了 CLI 的 _on_recv 回调。当 UDP 线程收到数据时，Backend 并不直接操作 UI（这会导致崩溃），而是发射 pyqtSignal。Qt 的主事件循环捕获信号后，安全地更新 UI 组件。

    优化策略: 针对 RK3566 较弱的 GPU，代码中包含 ZFEIQ_FORCE_SOFTGL 环境变量检测，强制使用软件渲染 OpenGL，并禁用了复杂的 UI 动画以提升响应速度。

4. 建议与评价 (Perspectives & Advice)
4.1 开发者自述 (My AI Perspective)

评价: 代码结构非常清晰，模块化做得很好。特别是将 cli 核心逻辑完全剥离，使得 GUI 和 TUI 可以共用同一套大脑，这是非常成熟的工程实践。加密部分的 Level B 实现虽然使用了明文交换种子（HKDF-only），但在局域网信任域内是一个很好的性能与安全的平衡点。

建议:

    并发安全: _sessions 和 history 等字典在多线程（UDP接收线程 vs 主线程）下访问，虽然 Python 有 GIL，但对于复合操作仍建议加 threading.Lock。

    异常处理: 文件传输的 download_file 循环中，异常捕获较宽泛，建议针对 ConnectionResetError 等网络异常做更细致的重试逻辑。

    测试覆盖: 目前测试脚本集中在 tests/ 目录，建议引入 pytest 并增加对 crypto.py 的单元测试覆盖率。

4.2 答辩老师视角 (Thesis Defense Teacher)

评价: "这个项目完整度很高，不仅实现了基本的即时通信，还结合了具体的硬件平台（RK3566）做了特色功能（OCR）。你提到的加密协议 Level B 设计，虽然不是业界标准的 TLS，但体现了你对密码学原语（HKDF, AES-GCM, Nonce派生）的理解和运用，这点在本科/硕士生项目中是加分项。"

建议 (刁钻问题预警):

    创新点: "除了复刻飞秋，你的核心创新点是什么？" -> 回答策略: 重点强调 跨架构适配（x86/ARM）、轻量级加密协议设计 以及 边缘侧 NPU 的异构计算应用。

    安全性: "KX1/KX2 明文交换种子如何防止中间人攻击？" -> 回答策略: 坦诚说明当前是基于“首次信任（TOFU）”或带外验证指纹的模型，Level B 侧重于会话的前向保密（部分）和防重放，而非强认证。

    性能: "在板子上跑 OCR 会卡顿吗？" -> 回答策略: 展示 NPU vs CPU 的推理耗时对比数据（你的代码里有计时逻辑）。

4.3 甲方视角 (Client / End User)

评价: "功能倒是挺全的，能发文件，能截图，还能识别文字，这在办公场景挺实用。特别是那个‘通讯已加密’的提示，让人感觉很安全。但是，界面（GUI）看起来还是有点像工程师用的工具，不够‘现代化’。"

建议:

    易用性: "能不能做一个‘一键安装包’？现在还要装 Python 环境、pip install，对我们要部署的非技术员工太难了。" -> 建议打包为 exe/AppImage。

    UI 美化: 现在的界面比较朴素，建议增加头像上传功能（目前似乎只是预留接口），并优化聊天气泡的样式。

    稳定: "我在断网或者 IP 变了的时候，它能自动重连吗？" -> 确认 _rebind 逻辑在用户无感知的层面是否足够健壮。

4.4 上市公司 CEO 视角 (CEO Perspective)

评价: "ZFeiQ 切中了一个细分市场：政企内部安全通信。现在很多企业不允许使用微信/钉钉传文件，飞秋又太老旧且不安全。你的产品支持国产化信创环境（麒麟系统 + 瑞芯微芯片），这非常符合当前的国产替代大趋势。"

建议:

    商业模式: 不要只做 IM。要把 OCR、文件传输打包成“安全办公协作套件”。

    护城河: 代码里的加密协议是私有的（虽然兼容 IPMSG），这是好事也是坏事。好事是可以卖“安全网关”，坏事是生态封闭。建议开发一个“网关版”，可以审计所有加密流量，这对企业客户非常有吸引力。

    扩展性: 既然已经跑通了 NPU，下一步能不能做本地会议录音转写？这也是 NPU 的强项，且办公需求巨大。

总结: ZFeiQ 是一个技术栈全面、工程实现扎实且具有鲜明硬件特色的优秀项目。它不仅仅是一个聊天软件，更是一个验证边缘计算、网络安全协议和跨平台 UI 开发的完整实验场。

---
