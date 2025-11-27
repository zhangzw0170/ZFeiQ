
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


## OCR/NPU 文字识别集成规划（PP-OCR v4 for RK3566）

本节为集成 PP-OCR v4 详细规划，原“项目要求（禁止修改）”保持不变。目标：在 RK3566（aarch64 Ubuntu Kylin）环境，利用 `PPOCRv4/build_output/` 下的 PP-OCR v4 检测/识别模型（ONNX/RKNN 格式）与 NPU 加速，实现截图与图片消息的快捷文字识别，并兼容 Windows/Linux 普通 PC（自动降级到 CPU）。

### 模型与工具来源
- 检测模型：`PPOCRv4/build_output/ocr_det_rk3566_v4.rknn`、`ocr_det_static.onnx`
- 识别模型：`PPOCRv4/build_output/ocr_rec_rk3566_v4.rknn`、`ocr_rec_static.onnx`
- 字典文件：`PPOCRv4/ppocr_keys_v1.txt`
- 后处理工具：`PPOCRv4/utils/db_postprocess.py`、`rec_postprocess.py`、`operators.py`
- 测试/转换脚本：`build_fp16_v4.py`、`gen_test_img.py`、`simulate.py`

### 0. 目标与使用场景

- 截图后一键“OCR”将识别的文本填入聊天输入框，可编辑后发送。
- 对已收到或待发送的图片/文件右键“提取文字 (OCR)”。
- CLI 模式新增命令：`/ocr <image_path>` 输出识别文本；可用 `--send` 直接群发。
- 可配置：自动识别截图开关、选择引擎（自动/NPU/CPU）、最大图片大小阈值、并发队列长度。

### 1. 代码结构调整

1. 新建目录：`zfeiq_ocr/`（抽取自 `PPOCRv4/utils/` 的核心推理与后处理），包含：
   - `__init__.py`
   - `engine.py`：统一封装加载、前处理、推理、后处理；暴露 `run(image)` 返回文本。
   - `runtime_npu.py`：NPU 推理（RKNN Lite2），加载 `ocr_det_rk3566_v4.rknn` 和 `ocr_rec_rk3566_v4.rknn`。
   - `runtime_cpu.py`：CPU/降级路径（初期用 `ocr_det_static.onnx` 和 `ocr_rec_static.onnx`，后续可用 ONNXRuntime）。
   - `postprocess.py`：整合 `db_postprocess.py`, `rec_postprocess.py`，负责 boxes 过滤、文本排序。
   - `utils_image.py`：图像加载、缩放、旋转检测。
   - `ppocr_keys_v1.txt`：字符集字典。
2. 保留 `PPOCRv4/` 作为模型和工具来源，后期可迁移/精简。
3. GUI：在 `zfeiq_gui/backend.py` 增加 OCR 调度接口；在截图/图片处理页面（或相关 `pages/` 下组件）增加触发按钮与异步回调。
4. CLI：在 `zfeiq_cli/cli.py` 中注册命令 `/ocr`，解析路径并调用 `OcrEngine.run`；增加参数 `--send`、`--raw`（只输出纯文本不加提示）。

### 2. 引擎设计与降级策略

`OcrEngine` 初始化流程：

```text
OcrEngine(mode='auto'):
   if mode == 'npu' or (mode=='auto' and arch=='aarch64' and rknn libs present):
      try load PPOCRv4/build_output/*.rknn 模型
      else fallback cpu
   elif mode == 'cpu':
      load PPOCRv4/build_output/*.onnx 模型（后续可用 ONNXRuntime）
   else: raise
```

运行时：

1. 前处理：统一 RGB、resize 不超过设定长边（默认 1600），保持宽高比；规范化到 float32。
2. 调用检测模型（PP-OCR v4 DB）-> 文本区域 boxes；过滤低分。
3. 对每个 box 裁剪，识别模型（PP-OCR v4 CRNN）推理 -> 文本 + 置信度。
4. 排序（行方向 + 左到右），合并结果；返回拼接文本与结构（供后续高亮）。
5. 性能：首次调用完成后缓存上下文；提供 `warmup()` 在 GUI 启动异步执行。

### 3. 并发与线程模型

- GUI：使用 `QThread` 或 `QThreadPool` + `QRunnable` 将 OCR 置于后台，完成后通过 signal 返回结果，避免阻塞 UI。
- CLI：使用 `ThreadPoolExecutor`（单 worker）或直接同步执行（初期）。识别任务入队，超过阈值拒绝并提示“OCR 繁忙”。
- 统一取消机制：若用户关闭对话框或撤销截图，可标记任务取消（后期迭代）。

### 4. 配置与状态持久化

新增持久化键（示例）：

```text
ocr_enabled: bool
ocr_mode: 'auto' | 'npu' | 'cpu'
ocr_autorun_on_screenshot: bool
ocr_max_image_side: int   # 默认 1600
```

- 在现有状态/配置管理（`state.py` 或 GUI 设置页）中添加；保存与加载与其他设置一致。
- GUI 设置页新增“文字识别”分组；显示当前引擎与模型加载状态（已加载/失败/降级）。

### 5. 依赖与安装策略

- 基础依赖新增：`numpy`, `Pillow`（若未包含）。
- NPU 专用：`rknn-toolkit-lite2`（仅 aarch64，用户手动安装 `.whl`，不直接放入通用 `requirements.txt` 以避免跨平台安装失败）。
- CPU 后端（计划第二阶段）：`onnxruntime`（跨平台）可选安装。

安装示例（RK3566）：

```pwsh
pip install numpy Pillow
pip install ./PPOCRv4/rknn_toolkit_lite2-1.6.0-cp38-cp38-linux_aarch64.whl
```

模型文件：
- RKNN 模型：`PPOCRv4/build_output/ocr_det_rk3566_v4.rknn`、`ocr_rec_rk3566_v4.rknn`
- ONNX 模型：`PPOCRv4/build_output/ocr_det_static.onnx`、`ocr_rec_static.onnx`
- 字典：`PPOCRv4/ppocr_keys_v1.txt`

环境变量：

```text
ZFEIQ_OCR_MODE=cpu|npu|auto   # 覆盖配置
ZFEIQ_FORCE_CPU_OCR=1          # 强制禁用 NPU
```

### 6. GUI 交互细节

- 截图完成后弹出预览窗口：添加“识别文字”按钮；识别成功后将文本插入输入框（不自动发送）。
- 图片消息（收到/发送框）右键菜单增加“提取文字”。
- 识别过程中显示微型进度旋转指示；失败弹出非阻塞 toast：“OCR 失败：<原因>”。
- 在聊天区显示可折叠的 OCR 结果块（带复制按钮）。

### 7. CLI 命令设计

```text
/ocr <path> [--send] [--raw] [--mode auto|npu|cpu]
```

- 无效路径：输出“路径不存在或不可读”。
- 识别结果为空：输出“未识别到文字”。
- `--send`：将结果作为普通消息广播（遵循加密/签名逻辑）。
- `--raw`：仅输出纯文本，无额外前缀。

### 8. 测试与验证

测试脚本：`tests/test_ocr_integration.py`

- 准备 2~3 张样例图片（含中英文）。
- 调用 `OcrEngine.run`，断言返回文本非空；在 aarch64 上验证 NPU 分支；在非 aarch64 上验证降级。
- 性能基准：记录首次加载耗时与单张图片平均耗时；写入日志。
- 并行测试：同时提交 2 个 OCR 请求（GUI/CLI），确认串行/队列行为符合设计。

### 9. 日志与故障处理

- 分类日志：`[OCR] init/load/detect/recognize/error`。
- 模型文件缺失：警告并自动禁用 OCR；提示用户放置模型至 `zfeiq_ocr/models/` 或保持原位置。
- 超大图片：先压缩再处理；记录压缩系数。
- 内存不足或 NPU 调用异常：捕获异常，回退 CPU 或提示“资源不足（已禁用 OCR）”。

### 10. 安全与资源控制

- 路径校验：仅允许普通文件，禁止目录与超过大小（默认 8MB，可配置）。
- 拒绝处理含可执行扩展（.exe/.sh 等）即使其是图片伪装；仅按魔数/`Pillow` 成功打开才继续。
- 避免日志中输出图片的完整 base64；仅记录尺寸与哈希摘要。

### 11. 迭代阶段划分

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| P1 | 抽象引擎 + NPU 路径最小实现 | engine + 手动命令行测试 |
| P2 | CLI `/ocr` 命令 + 基础配置持久化 | 更新 CLI & state |
| P3 | GUI 按钮 + 异步线程 + 结果展示 | 前端交互完成 |
| P4 | 测试脚本 + 日志与错误处理完善 | 测试与基准数据 |
| P5 | CPU ONNXRuntime 路径 & 自动截图 OCR | 跨平台增强 |
| P6 | 结果结构化（坐标高亮）与批量图片识别 | 高级功能 |

### 12. 风险与缓解

- 跨平台依赖安装失败：将 NPU 依赖列为“手动安装”，不放入通用 requirements；README 分平台说明。
- 模型加载耗时：提供异步 `warmup()`；首次使用前 UI 反馈“正在预热”。
- 性能瓶颈（多并发）：当前串行；后续可加简单队列与丢弃策略。
- 识别准确率不足：允许用户在设置中调节检测阈值、最大长边；暴露高级配置（第二期）。

### 13. 最小落地清单（P1-P3 必要文件）

```text
zfeiq_ocr/
   __init__.py
   engine.py
   runtime_npu.py
   runtime_cpu.py
   postprocess.py
   utils_image.py
   ppocr_keys_v1.txt
PPOCRv4/build_output/ocr_det_rk3566_v4.rknn
PPOCRv4/build_output/ocr_rec_rk3566_v4.rknn
PPOCRv4/build_output/ocr_det_static.onnx
PPOCRv4/build_output/ocr_rec_static.onnx
tests/test_ocr_integration.py
```

README 与设置页同步增加使用说明与安装提示。

### 14. 后续可选增强

- 图片内多语言自动检测与分语言识别。
- 聊天记录 OCR 索引（全文检索图片中的文字）。
- 批量文件拖拽后自动合并 OCR 结果成单条消息。
- 离线缓存识别结果（哈希命中直接返回）。

## 版权声明

本项目仅用于学习与交流，禁止用于违法场景。欢迎反馈建议。

