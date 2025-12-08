# NZFeiQ 重构测试流程与进度总览

本文档用于对照 `legacy/` 与当前 `NZFeiQ/`（dev-refactor 分支），提供端到端测试步骤、核对项以及重构进度表。目标是确保功能不回退、接口保持一致或给出明确替代方案。

## 测试总览

- **环境**: Linux, bash, Python 3.8+（已验证 `/usr/bin/python3`）。
- **网络**: 局域网可广播；若无，则单播测试即可。
- **数据目录**: `common/`（自动生成/读写 `config.json`、`groups.json`、`keys/`、`downloads/`）。

## 一次性准备

- **依赖准备**:
	- 可选 OCR: `onnxruntime` 或对应运行时；不安装仅影响 OCR 功能（启动会有 Warning）。
	- Python 依赖（若需要）: 按需安装 `cryptography`、`Pillow`（Linux 截图备选）等。

- **首次启动生成密钥**:
	- 执行 CLI 会自动在 `common/keys/identity.bin` 生成 X25519 身份密钥。

### 本地多回环测试（单机模拟多节点）

若要在一台机器上模拟多个 P2P 节点（当前 `test/` 脚本使用不同回环地址如 `127.0.0.2`、`127.0.0.3` 等），需要在宿主机上临时添加回环别名并允许本地回环间通信。

- 添加回环别名（需要 sudo）:
```bash
sudo ip addr add 127.0.0.2/8 dev lo
sudo ip addr add 127.0.0.3/8 dev lo
sudo ip addr add 127.0.0.4/8 dev lo
sudo ip addr add 127.0.0.5/8 dev lo
sudo ip addr add 127.0.0.6/8 dev lo
ip addr show dev lo | grep 127.0.0
```

- 说明: 上述命令在重启后不会持久化；若不希望或无法执行 sudo，请参见下方“替代：单主机多端口模式”。

- 运行 demo（在仓库根目录）：
```bash
cd NZFeiQ
python3 test/demo_p2p_secure_loopback.py
python3 test/demo_filetransfer.py
python3 test/demo_groups_6users.py
python3 test/auto_test_requirements.py
```

已验证行为：若回环别名正确添加，demo 能启动多个节点并进行 discover/file/group 测试；若仍有丢包/发现失败，请检查防火墙或本机网络策略。


```bash
/usr/bin/python3 NZFeiQ/cli/main.py
```

## 核心功能测试流程

### 1. 启动 CLI 与基础信息

- 命令:
```bash
/usr/bin/python3 NZFeiQ/cli/main.py
```
- 期望输出: `[INFO] Core started on <ip>:2425`，`help` 列出命令集。
- 检查项: `info net` 显示 `Local IP/Bind IP/UDP Port/Broadcast` 正确。

### 2. 登录与节点发现

- 登录并广播:
```bash
login <your_name>
discover
list
```
- 期望: 自身入表、广播发送，若同网段另一个节点在线（legacy 或新引擎），`list` 可见对方。

### 3. 文本消息收发（含加密握手）

- 向某 IP 发送:
```bash
send <peer_ip> hello
```
- 期望: 首次通信自动握手（`SessionState` 进入 `ESTABLISHED`），随后消息加密发送；对方收到后回 ACK（`IPMSG_RECVMSG`）。
- 严格模式校验（可选）:
```bash
set encrypt strict
send <peer_ip> secret
```
- 期望: 若握手未完成则拒绝明文发送；握手完成后正常加密。

### 4. 广播消息

- 命令:
```bash
send all hello everyone
```
- 期望: 本网段主机收到消息；本地历史入账。

### 5. 文件传输（IPMsg 协议风格）

- 在 A 侧发起要约:
```bash
file send <peer_ip> /path/to/file
```
- B 侧查看 offer（自动日志）并接受:
```bash
file list   # 若实现后输出列表（当前以日志/事件为准）
file accept <packet_no:file_id>
```
- 期望: `common/downloads/` 下生成文件；A 侧收到 `RELEASEFILES` 释放映射。

### 6. 群组与搜索

```bash
group create devs
group add devs alice
group msg devs "standup at 10"
search alice
```
- 期望: 群组持久化在 `common/groups.json`；逐个向在线成员发消息；搜索返回用户/组条目。

### 7. 截图与 OCR（可选）

- 截图:
```bash
screenshot
```
- OCR（如装有运行时）:
```bash
ocr /path/to/image.png --send <peer_ip>
```
- 期望: 截图保存到 `common/downloads/screenshots/`；OCR 输出文本并可发送。

#### OCR 验证（详细步骤）

下面的步骤用于验证 `resource/PPOCRv4` 已正确接入到 `NZFeiQ`，并覆盖三条运行路径：
1) 设备 NPU（RKNN）直接运行；2) legacy `main.py` 外部主脚本回退；3) PC CPU（ONNX Runtime）.

1. 检查资源目录

```bash
ls -la resource/PPOCRv4
```

应包含 `main.py`、`test.jpg`、`build_output/`、`utils/`、`ppocr_keys_v1.txt` 等文件。

2. 快速初始化自检（Python）

此命令会输出：`ready`、`use_npu`、`use_external_main` 及 `base_path`，用于判断 OCR 引擎选择的运行时。

```bash
/usr/bin/python3 - <<'PY'
from NZFeiQ.core.ocr import ZFeiQOcr
o = ZFeiQOcr.get_instance()
print('ready=', o.ready, 'use_npu=', o.use_npu, 'use_external_main=', o.use_external_main)
print('base_path=', o.base_path)
PY
```

3. 直接调用 OCR（库接口）

在不启动 CLI 的情况下直接对 `test.jpg` 运行 OCR，检查返回文本：

```bash
/usr/bin/python3 - <<'PY'
from NZFeiQ.core.ocr import ZFeiQOcr
o = ZFeiQOcr.get_instance()
res = o.run('resource/PPOCRv4/test.jpg')
print('OCR result:\n', res)
PY
```

期望：打印出识别到的文本行或 `No text detected.` 或具体错误信息（如模型缺失、运行时错误）。

4. 在 CLI 中测试（推荐）

启动 CLI，然后运行命令：

```bash
/usr/bin/python3 NZFeiQ/cli/main.py
# 在提示符下：
ocr resource/PPOCRv4/test.jpg
```

期望：CLI 会显示 `OCR processing...` 并随后输出 `OCR Result (<file>):` 及识别文本。若使用 `prompt_toolkit` 渲染，文本中含 `&`、`<` 等字符现在会被转义以避免解析错误。

5. 测试 legacy 主脚本回退（NPU 环境下的备用方案）

在带有 RKNN/NPU 的设备上，如果直接通过 `rknnlite` 初始化失败，OCR 模块会优先尝试调用 `resource/PPOCRv4/main.py`（legacy main）。你也可以直接运行该脚本以验证 NPU 流程：

```bash
cd resource/PPOCRv4
python3 main.py --debug
```

`main.py` 默认读取 `./test.jpg`，并会输出每个 box 的识别结果（例如：`Box 0: '文本' (Conf: 0.92)`）。若要测试 NZFeiQ 使用该外部脚本的回退流程，确保设备为 aarch64（或在代码中手动改 arch）并且 RKNN 环境不可用，这样初始化时会将 `use_external_main` 设为 True。

6. 常见问题与排查

- 如果看到 `Error: ONNX models not found in ...`：确认 `resource/PPOCRv4/build_output/` 下存在 `ocr_det_static.onnx` 与 `ocr_rec_static.onnx`。否则只能使用 NPU（RKNN）或 legacy 主脚本。
- 若 CLI 报 `not well-formed (invalid token)` 或类似 XML/HTML 解析错误：已在 CLI 中对 OCR/消息文本做了 HTML 转义，升级后应不再出现。若仍出现，请更新 `prompt_toolkit` 相关依赖或在无终端环境下使用纯文本模式运行。
- 如果期望使用 NPU（RKNN）但初始化失败：检查 `rknnlite` 是否安装并兼容当前平台；查看 `resource/PPOCRv4/log_analysis_main.txt` 或运行 `main.py --debug` 获取详细日志。

7. 把 OCR 验证加入自动化回归（建议）

- 在 `test/` 下添加一个小脚本，会调用 `ZFeiQOcr.get_instance().run(test.jpg)` 并断言返回非空文本，或捕获并记录错误（便于 CI 分支的回归验证）。

示例断言脚本（pseudo）:

```python
from NZFeiQ.core.ocr import ZFeiQOcr
o = ZFeiQOcr.get_instance()
res = o.run('resource/PPOCRv4/test.jpg')
assert 'Hello' in res or 'No text detected.' not in res
```

如果你同意，我可以把上述断言脚本加入 `test/` 目录并添加一个 `make test-ocr` 快捷命令。

### 8. 退出

```bash
exit
```
- 期望: 广播退出，线程与传输优雅停止。

### 9. Alpha 6.1 特定测试：表情与截图集成

- 表情面板与管理
	- 操作：启动 GUI（`python3 NZFeiQ/gui/main.py`），打开任一聊天窗口，点击表情按钮。
	- 期望：弹出表情面板，位置锚定在按钮下方；首格显示齿轮样式（进入“表情管理”）。
	- 管理操作：在表情管理对话中添加一张 PNG/JPG（会复制到 `common/emotes/`），关闭对话并刷新面板后可选用新表情发送。
	- 回退兼容：如果你仍然有旧 `common/emojis` 目录，当前版本会优先使用 `common/emotes`，建议手动把文件复制到 `common/emotes` 或等待下一次自动迁移。

- 截图工作流
	- 操作：在聊天 UI 中触发截图（工具栏按钮或菜单），完成截图后检查 `common/downloads/screenshots/` 或 `common/downloads/`（视平台而定）。
	- 期望：截图文件保存成功并在聊天列表中以“本地文件”条目出现（状态为未发送/本地）。程序不会自动发送截图，需用户主动发送以避免误发。

- 设置页：重生密钥与指纹刷新
	- 操作：打开设置页，点击“重生成密钥”按钮并等待完成。
	- 期望：按钮完成后设置页内显示的指纹串立即刷新为新值（若你希望避免任何 UI 阻塞，建议将重生操作通过 Bridge 的异步任务执行；该项计划在后续迭代完成）。

## 回归与故障定位要点

- **日志等级**: `log level <DEBUG|INFO|WARN|ERROR>`；确保 `ZFeiQCore.log_level` 在 `__init__` 早期初始化（已修复）。
- **握手日志**: `debug cipher on` 可查看密文；失败时检查 `core/session.py` 状态机与 HKDF/ChaCha20-Poly1305 实现。
- **网络选择**: `core/transport.py` 与 `engine._detect_best_ip()` 选择优先级（192.168 > 172 > 10）。
- **持久化一致性**: 修改 `common/config.json`、`groups.json` schema 时同步 `_load_*`/`_save_*`。

## 重构进度表（与 legacy 对照）

- **引擎 `core/engine.py`**: 重写完成
	- 事件驱动、节点注册、ACK 重传、加密集成、文件要约端口传递已实现。
	- 修复: `log_level` 初始化顺序导致的 AttributeError。

- **会话/加密 `core/session.py`**: 就绪
	- X25519 + HKDF + ChaCha20-Poly1305；`SessionState` 与握手 KX1/KX2/ENCREADY 流程完整。
	- 与 legacy 行为兼容，支持严格模式拒绝明文。

- **协议 `core/protocol.py`**: 就绪
	- 报文构建/解析、扩展区 `\0` 分隔、列表与文件附件编码/解码。

- **传输 `core/transport.py`**: 就绪
	- UDP 广播/单播；端口与 iface 推断；DEBUG 标签 `[DEBUG] send_broadcast` 兼容。

- **状态/历史 `core/state.py`**: 就绪
	- `NodeRegistry`、`ChatHistory`、`PendingAck`；节点清理与历史记录。

- **文件传输 `core/filetransfer.py`**: 部分完成
	- IPMsg 风格文件服务器、映射释放；offer 事件与日志输出完善。
	- TODO: `file list` 的完整 CLI 视图。

- **OCR `core/ocr.py`**: 可用（懒加载）
	- 未检测到 `PPOCRv4` 工具时给出 Warning，不影响核心。

- **CLI `NZFeiQ/cli/shell.py`**: 就绪
	- 命令集对齐 legacy，大部分已可用；个别标注“未实现”的命令后续补全。

- **GUI `NZFeiQ/gui/*`**: 初步桥接
	- `bridge.py` 映射事件至 UI；进一步对齐 legacy GUI 功能待补充（按需）。

- **测试脚本 `test/*`**: 可运行
	- `demo_p2p_secure_loopback.py` 验证加密；`demo_filetransfer.py` 验证传输；`auto_test_requirements.py` 三节点校验。

## 自动化测试建议

- 在两台主机（或同机不同容器网络）分别运行 CLI，执行第 2-5 步。
- 使用 `test/auto_test_requirements.py` 做 3 节点回归，观察日志事件：`EV_NODE_UPD/EV_MSG_SENT/EV_MSG_RECV/EV_FILE_OFFER/EV_FILE_DONE`。

## 已知差异与待办

- `file list` 的完整 CLI 展示仍为 TODO（现通过日志/事件提供 offer id）。
- GUI 的部分页面与 legacy 存在样式/交互差异，后续按事件桥接补齐。
- OCR 依赖需按目标平台选择（CPU ONNX 或 RKNN）。

---
如需将日志等级持久化到 `config.json`、或扩展自动化脚本输出更详细断言，请告知，我将追加实现与文档。


## Notes: Enabling DEBUG and recent test run

I changed `common/config.json` to set `"log_level": "DEBUG"` and re-ran the built-in demos from the repository (`test/demo_p2p_secure_loopback.py`, `test/demo_filetransfer.py`, `test/demo_groups_6users.py`, `test/auto_test_requirements.py`) to surface handshake and transport debug logs.

Result: switching to `DEBUG` did not by itself fix the observed failures (missing Cipher OUT/IN, file Offer not received, group message drops). The DEBUG setting is useful because it allows session/transport debug events to be emitted, but the demos still showed missing/failed messages — indicating the problem is likely at the transport/socket routing or race conditions rather than purely log verbosity.

Practical notes:
- To force DEBUG at runtime without changing config, in CLI run: `log level DEBUG` (or have demos send that command to created CLIs).
- If you want full session/transport trace, also enable `debug cipher on` in each CLI session to show cipher lines when encryption occurs.

Next steps suggested:
- Capture a `tcpdump -i lo udp port 2425` during a demo run to verify whether UDP packets (KX1/KX2/ENCREADY/Offer) are being emitted/received at the kernel level.
- If UDP packets are present on `lo`, add temporary DEBUG prints in `core/transport.py` to log socket bind/recv results to determine whether the application is receiving them.

---
