**ZFeiQ — Release Notes: Alpha 6.2 (相较 Alpha 4.0 的主要变化)**

发布时间：2025-12-26

简要概览：Alpha 6.2 以稳定性修复与可移植性改进为主，并开始为握手签名（handshake auth）与 CI 测试铺路。主要改动集中在消息路由、截图行为、配置容错、文档重构与测试模板新增。

- **关键错误修复**：修复了发送流程中导致的 KeyError（因直接索引 `current_target['ip']` 导致）。相关修复位于 `NZFeiQ/gui/chat.py`，避免因缺失字段崩溃。

- **群组消息语义变更**：将群组发送逻辑改为针对在线成员的逐一单播（per-member unicast），并对入站群组消息使用统一前缀 `[Group:<群名>]` 进行本地路由以保证群组消息只出现在群组窗口（接收端会去掉前缀显示）。相关改动在 `NZFeiQ/gui/chat.py` 中。

- **历史与视图一致性**：在加载个人聊天历史时，跳过带有群组前缀的记录，避免群组消息重复出现在个人会话视图中。

- **截图处理行为调整**：本地截图保存后不再自动插入到聊天窗口；改为在界面底栏展示保存路径，防止误发送或混淆会话（`NZFeiQ/gui/chat.py`）。

- **配置容错与可移植性**：`download_dir` 配置现在仅在目标主机存在时生效；否则回退到仓库内的默认目录（`common/downloads`），减少因开发机绝对路径导致的运行故障（`NZFeiQ/core/engine.py`）。

- **关于页与版本信息**：在关于/运行环境一栏增加了 `Python` 前缀，改善运行时可读性（`NZFeiQ/gui/settings.py`）。同时将核心版本号提升为 `Alpha 6.2`（更新于 `NZFeiQ/core/__init__.py`）。

- **文档重构与安全设计合并**：合并并整理了加密与迁移相关文档为 `docs/SECURITY.md`，保留迁移说明的跳转提示；新增握手认证设计文档 `docs/HANDSHAKE_AUTH.md`，描述后续计划中签名化握手的方案与 TOFU 策略。

- **测试与 CI 准备**：添加了 `test/test_handshake_auth.py`（pytest 模板）与 `docs/CI_TESTS.md`，为在 CI 中验证握手签名、密钥 API 与集成测试提供起点。

- **依赖与打包**：新增仓库根级简化依赖文件 `requirements.txt`，便于快速搭建运行环境（非详尽列表，参见 `docs/` 内的原始依赖清单以做复核）。

- **后续工作与注意事项**：
  - 必需：在目标环境执行 GUI 验证以确认群组发送、接收与截图行为（需用户交互）。
  - 计划：在 `NZFeiQ/core/crypto.py` 中实现签名/验证（例如 Ed25519），并将签名附加到握手消息（KX1/KX2），同时在 `NZFeiQ/core/session.py`/`engine.py` 中增加验证逻辑和 TOFU 管理 UI。
  - 建议：在 CI 中添加针对握手签名、回放攻击与回退策略的自动化集成测试。

如需我把这份发布说明提交到仓库（创建提交并 push），或同时生成 Release 页面草稿（GitHub release notes），我可以继续完成这些步骤。
