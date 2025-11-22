# CLI → Core 映射（命令对照与差异）

说明：本文件列出原有 CLI 命令（基于 `CHANGELOG.md` 的描述）如何映射到重构后的 `ZFeiQCore` API，标注当前 Core 已覆盖的功能、需要在 Core 补充的接口，以及应由 CLI 适配器维护的行为（例如提示符与交互细节）。

---

## 1. 全局说明

- Core 负责：网络协议实现（UDP/TCP）、消息解析/封装、密钥管理、文件服务、历史持久化、事件发布。
- CLI 负责：命令解析、用户交互（提示符、重绘、输入缓冲）、参数默认值与 UX（例如 `/clear`、下载目录选择）、以及把 CLI 命令调用映射为 Core API。
- 映射目标：`ZFeiQ_Python/zfeiq_core/api.py` 中的 `ZFeiQCore`（方法示例：`login`, `send_message`, `get_history`, `ensure_keys`, `attach_network`, `attach_protocol`, `attach_file_service`, `register_file`, `unregister_file`）。

---

## 2. 命令映射表

- `/discover`（广播发现）
  - Core API: `core.network.broadcast_discover()` 或通过 `core.send_message(..., to='all', cmd='BR_ENTRY')`（实现内的网络服务应暴露广播接口）
  - Core 已覆盖: NetworkService 支持广播；ProtocolService 可解析 BR_ENTRY
  - CLI 适配器: 触发广播并监听 `events.TOPIC_UDP_RECEIVED` 或 `TOPIC_MSG_INCOMING`，在控制台打印在线列表
  - 需补充/注意: 如果存在 `--bind` 限制或跨子网单播发现，应在 CLI 层解析参数并调用 `core.network.unicast_discover(ip)`。

- `/info [group:<name>|net|set]`
  - Core API: `core.get_history(group=name)`（group 历史），`core.network.get_status()`（网卡/绑定信息），`core.get_config()`（download_dir 等）
  - Core 已覆盖: history/get_history; network 状态接口需在 NetworkService 暴露
  - CLI 适配器: 格式化输出为原 CLI 风格（包含在线人数、download_dir 等）

- `/send all <text>` 或 旧 `/sendall <text>`
  - Core API: `core.send_message(text, to='all')` 或 `core.send_message_broadcast(text)`
  - Core 已覆盖: `send_message`（可实现单播/广播策略）
  - 需补充: 精确行为（是否遍历在线列表并单播 vs 使用广播）由 CLI 配置，Core 应提供两种模式或由 network 层策略参数控制。

- `/send user:<name|ip> <text>`
  - Core API: `core.send_message(text, to=target)`（target 可为 ip 或 username）
  - Core 已覆盖: send_message 接口
  - CLI 适配器: 将用户名解析成 IP（通过 core 的在线列表查询）并调用 `send_message`。

- `/group <name> -add|-delete [username]` / `/group <name> -send <text>`
  - Core API: 目前 Core 未实现 Group 管理 API
  - 需要在 Core 中补充: `core.group_add(name, username)`, `core.group_remove(name, username)`, `core.group_send(name, text)` 或将组管理保持为纯 CLI 本地结构并由 CLI 在发送时迭代调用 `core.send_message`
  - 建议: 将组管理放在 CLI 层实现以加快验证；若需 Core 层统一管理（跨客户端共享组），需扩展 Core 并设计同步协议字段。

- `/file send user|ip <path>`
  - Core API: `core.file_service.register_file(path, owner=me)` 然后发送带 FILE_OFFER 的消息：`core.send_message(text=FILE_OFFER_META, to=target)`
  - Core 已覆盖: FileService 支持注册映射并在 2425/TCP 上响应 `GETFILEDATA`；ProtocolService 能生成 FILEATTACH
  - CLI 适配器: 负责文件路径检查、readable 权限、计算 attach_id、调用 `core.register_file` 并显示要约信息

- `/file list`
  - Core API: `core.file_service.list_offers()` 或 CLI 本地维护已发送/已接收要约列表
  - Core 已覆盖: FileService 注册/注销接口存在；需暴露列表接口

- `/file accept <id>`
  - Core API: `core.file_service.accept_offer(offer_id, dest_dir)` 或 CLI 发起 `GETFILEDATA` 到目标 IP:2425
  - Core 已覆盖: TCP GETFILEDATA 服务端实现；但接收端主动拉取实现需在 CLI 适配器中执行（或 Core 提供方便方法 `core.download_file(remote_ip, packet_no, attach_id, dest)`）
  - 建议: 在 Core 中添加 `download_file(remote_addr, packet_no, attach_id, dest_path)` 以便统一错误处理与事件发布（进度/完成）

- `/file cancel <id>`
  - Core API: `core.file_service.cancel_offer(offer_id)`
  - Core 已覆盖: unregister_file 存在；需保证事件发布（offer cancelled）

- `/set download_dir <path>`
  - Core API: `core.set_config('download_dir', path)` 或 `core.persistence.set('download_dir', path)`
  - Core 已覆盖: persistence/config 尚需明确接口
  - CLI 适配器: 验证目录并通知 Core，更新运行时默认

- `/set status online|busy|away`
  - Core API: `core.set_status(token)` 并广播 BR_ENTRY 带上状态扩展字段
  - Core 已覆盖: NetworkService 可发送 BR_ENTRY；需要 `core.set_status` 接口

- `/set bind <ip>`
  - Core API: `core.network.set_bind(ip)`（切换绑定并重新启动 socket）
  - Core 已覆盖: NetworkService 支持 bind 行为；需暴露并实现自动 rebind 限制开关（若用户显式 bind，应禁用自动 rebind）

- `/set keepalive <sec>` & `/set expire <sec>`
  - Core API: `core.set_config('keepalive', sec)` 与 `core.set_config('expire', sec)`，并由 NetworkService 使用这些值
  - Core 已覆盖: keepalive loop 存在；需暴露配置接口

- `/logout` / `/exit` / EOF（退出）
  - Core API: `core.logout()`：发送 `BR_EXIT`（广播 + 对已知节点单播），并关闭网络/文件服务
  - Core 已覆盖: 必须确保 NetworkService 支持单播下线行为

- `/discover ip:<addr>`（单播发现）
  - Core API: `core.network.unicast_discover(ip)` 或 `core.send_message(..., to=ip, cmd='BR_ENTRY')`
  - Core 已覆盖: NetworkService 支持单播发送

- `/info net`（打印绑定/广播地址/网卡/前缀）
  - Core API: `core.network.get_bind_info()`
  - Core 需补充: 暴露足够的网络诊断信息

- `/search user:<name>|group:<name>|ip:<addr>`
  - Core API: `core.search_users(name=..., ip=..., group=...)`（基于内存 registry）
  - Core 已覆盖: registry 存储用户信息；需添加搜索接口

- `/clear`（清空当前输入并重绘提示符）
  - CLI 责任：不应在 Core 实现

- `/set debug on|off`, `/set trace on|off`, `/set language zhCN|enUS`
  - Core API: `core.set_config('debug', True|False)` 等或 CLI 层控制日志/翻译

---

## 3. 核心差异与建议优先改进项（用于验证通过的核心能力）

- 组管理（`/group`）：目前 Core 未实现共享组管理；建议先在 CLI 层实现组集合并在发送时逐用户调用 `core.send_message`，待确认是否需要跨节点同步再将其上移到 Core。

- 文件下载主动作业（接收端主动向 2425/TCP 拉取）：当前 Core 实现了 2425 服务端与注册映射；建议补充 `core.download_file(remote_addr, packet_no, attach_id, dest_path)`，以便统一进度事件（`file.progress`/`file.complete`）。

- 网络诊断/绑定信息接口（`/info net`）需在 NetworkService 明确暴露（包括本地所有 IPv4、prefix、计算出的广播地址、当前 bind ip、port）。

- 自动 rebind 策略与用户显式 `--bind` 优先语义：Core 已有 auto-rebind 考虑（参考原 `cli.py` 的 `_auto_rebind_consider`），但需要在 `core.network` 中实现开/关开关，并确保 CLI 显式设置会写入配置（`persistence`）。

- 事件与日志级别：CLI 需要订阅 Core 的事件并以原样式打印（上线/下线/收到文件要约/接收进度）。Core 应发布统一事件（topic）包括：`msg.incoming`, `file.offer`, `file.progress`, `node.online`, `node.offline`, `keys.ready`。

---

## 4. 验证计划（最小回归场景）

1. 启动 Core（`ZFeiQCore`）并 attach Network/Protocol/File/History/ Crypto 服务。
2. 使用 CLI adapter 执行：`/discover` -> 检查是否在 5s 内发现本地回环或其它 demo 节点（事件 `node.online`）。
3. `/send user:<ip> hello` -> 对端是否收到 `msg.incoming`（并记录到 history）。
4. `/send all hello` -> 多端/回环验证广播或单播实现一致性。
5. `/file send user <path>` -> 触发 FILE_OFFER，要约到达接收端；接收端执行 `/file accept <id>`，调用 `core.download_file` 并在下载完毕触发 `file.complete`，数据比对通过。
6. `/logout` -> 对已知节点广播/单播 `BR_EXIT` 并在对端打印下线事件。

---

## 5. 下一步与任务分配

- 我（助手）将：
  1. 基于此映射实现 `ZFeiQ_Python/zfeiq_cli/adapter.py`（最小可运行骨架，命令解析 + 调用 `ZFeiQCore` + 订阅事件并打印）。
  2. 运行验证计划中的回归场景并记录差异。

- 请确认：是否把 `group` 功能先留在 CLI 层实现（推荐），或者希望我把 group 管理直接加到 Core？

---

附：若需我现在开始实现 CLI adapter 并运行最小回归测试，请回复“现在开始实现”，我会接着创建文件并执行 demo 测试。