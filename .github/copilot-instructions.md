# ZFeiQ — Copilot 指南（为 AI 代理量身）

目标：让代码代理快速上手并安全高效地在此仓库内修改代码。内容只覆盖可从代码中发现的约定、运行方式与示例路径。

- 项目大局：本仓库有两条主线：`legacy_ZFeiQ/`（历史参考）与 `NZFeiQ/`（当前开发主线）。核心模块集中在 `NZFeiQ/core/`（协议、传输、会话、文件传输、OCR 接口），UI 分为 `NZFeiQ/gui/`（PyQt5）与 `NZFeiQ/cli/`（无 UI 的生命周期与测试脚本）。

- 常用运行命令（在仓库根）：
  - 安装依赖： `python3 -m pip install -r requirements.txt`
  - 启动 GUI： `python3 NZFeiQ/gui/main.py`
  - 启动 CLI： `python3 NZFeiQ/cli/main.py`

- 架构要点（快速定位文件）
  - 协议与传输：`NZFeiQ/core/protocol.py`、`NZFeiQ/core/transport.py`。
  - 加密与会话：`NZFeiQ/core/crypto.py`、`NZFeiQ/core/session.py`。
  - 文件传输：`NZFeiQ/core/filetransfer.py`（TCP 端口与 `_attach_map` 语义需一致）。
  - UI 与桥接：`NZFeiQ/gui/backend.py`（后端到 UI 的桥），界面在 `NZFeiQ/gui/pages/`。
  - OCR/资源：`resource/PPOCRv4/` 与 `NZFeiQ/core/ocr.py`（可能调用 NPU/ONNX）；示例脚本在 `resource/`。

- 项目特定约定（发现自代码）
  - 默认端口 `2425` 被广泛假定为 IPMSG 通信端口，勿随意更改测试用例。
  - 字符解码顺序为 `utf-8` → `gbk` → `cp936` → `latin-1`（参见解码工具函数）。
  - 私钥懒生成且通常写入项目 key 目录；切勿把私钥打印到日志。
  - 广播/单播在 Linux 与 Windows 上绑定差异明显，修改 `transport.py` 后需在两个平台上验证。

- 常见改动示例（如何做到可验证的改动）
  - 新增 IPMSG 命令：修改 `NZFeiQ/core/protocol.py`（常量 + 编/解码），在 `NZFeiQ/core/session.py` 或 `NZFeiQ/core/engine.py` 添加处理逻辑，若需 UI 展示同步更新 `NZFeiQ/gui/backend.py` 与对应页面。
  - 调整传输行为：改 `NZFeiQ/core/transport.py` 并使用 `test/demo_*` 或 `test/` 下的演示脚本进行端到端验证。
  - 文件传输问题：优先检查 `_attach_map`、TCP 监听端口与 `filetransfer.py` 的回调契约，再用回环测试脚本验证。

- 调试与测试命令（代码中可查到的脚本）
  - 查阅并运行 `test/demo_filetransfer.py`、`test/demo_groups_6users.py`、`test/demo_p2p_secure_loopback.py` 进行集成级手动验证。
  - 关注 `NZFeiQ/zfeiq_history.json`、`zfeiq_state.json` 做状态恢复相关测试。

- 设计与变更注意事项（代理必须遵守）
  - 变更网络/传输/加密相关代码前必须写复现脚本并在至少两台进程/机器上验证。
  - 不要在 PR 中一次性提交大量跨层变更（core + gui + tests）；拆分小步骤并附带验证脚本。
  - 保留向后兼容的 `'legacy_ZFeiQ/'` 参考实现，不要删除历史实现，除非确认已迁移对应功能。

参考：仓库根 README 与 legacy 指南保留了更多背景（参见 `legacy_ZFeiQ/.github/copilot-instructions.md`）。

请审阅此草案：指出需补充的主题（例如 OCR/NPU 流程、CI 命令、常用调试日志路径）。
