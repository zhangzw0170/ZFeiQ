# 功能更新日志（超详细）

以下记录基于本阶段（至 2025/11/02 晚）所有实现与调优，时间采用 24 小时制，涵盖功能、UX、跨子网/多网卡增强、文件互通与文档同步。

## 2025/11/01 09:50 — 11:10 初版群发与分组

- 新增：`/sendall <text>` 群发（内部遍历在线列表单播）。
- 新增：分组管理 `/group <group_name> -add [username]` 与 `-delete [username]`；空参数分别表示“创建/删除群组”。
- 新增：`/group <group_name> -send <text>` 群组逐个单播（离线/重名用户跳过，自身跳过）。
- 文档：README 增加“单机双端测试（Windows + WSL）”章节。

## 2025/11/01 13:20 — 14:00 端口与多网卡基础支持

- 端口占用友好提示：捕获 Windows `[WinError 10013]`，提供关闭占用/改端口/WSL 双端等方案。
- 命令行：`--port <number>` 与环境变量 `ZFEIQ_PORT`。
- 多网卡：`--bind <本地IP>` 启动参数，推导定向广播地址，确保广播/单播走目标网卡。
- 文档：README 补充用法与排障说明。

## 2025/11/01 21:30 发现/状态/语言与基础诊断

- 统一 `/info`（移除 `/sysinfo`）；`/discover` 广播后自动展示在线列表。
- 新增 `/info group:<name>`（旧语义，后续变更为“群聊历史”）。
- 上下线提示：首次发现上线、收到 `BR_EXIT` 时打印“上线/下线”。
- 在线稳定性：
  - 保活：登录后每 30s 广播一次 `BR_ENTRY`；
  - 清理：90s 未更新的节点自动移除并提示“超时下线”。
- 在线状态：`/set status online|busy|away`，通过扩展字段 `status=<v>` 传播，非 online 在列表加标记。
- 调试开关：`/set debug on|off`、`/set trace on|off`。
- 语言骨架：`/set language zhCN|enUS`。
- GETLIST/ANSLIST：同实现间共享在线列表（扩展字段传输）；常量为预留值。
- 文档：README 同步命令、行为、排障内容。

## 2025/11/02 10:30 UX 与基本文件传输（实验）

- 提示头刷新：当有外部事件（消息/上下线/状态变更），丢弃未提交输入并重绘提示符；新增 `/clear`。
- 能力协商：广播 `cap=ack`；仅向声明支持 ACK 的对端请求 SENDCHECK，避免对飞秋误重传。
- 缺席用 `BR_ABSENCE`（`/set status away` 时）。
- 命令变更：废弃 `/sendall`，统一 `/send all <text>`。
- 文件（实验）：
  - `/file send user|ip <path>`、`/file list`、`/file accept <id>`；
  - 文本消息内携带 `FILE_OFFER;...` 元数据，接收端通过一次性 TCP 端口下载。
- 文档：README 同步以上变更与策略。

## 2025/11/02 18:30 Alpha 2.0：与飞秋/IPMSG 的基础文件互通

- 发送端：除 `FILE_OFFER` 外，同时发送附带 FILEATTACH 的 `SENDMSG`（兼容 BEL 分隔）；
- 接收端：解析附件并呈现可接受要约；
- 下载端：向 2425/TCP 发送 `GETFILEDATA`（`<packet_no>:<attach_id>`）主动拉取；
- 服务端：内置极简 2425/TCP 服务（登记映射后应答下载）；
- 互通性：与飞秋基本互通的文件收发；
- CLI：新增 `/file cancel <id>`；`/file accept` 默认保存目录服从 `/set download_dir` 或当前目录；`/info set` 输出含 `download_dir`、`time_format`；
- 测试：`tests/test_intraapp_download.py`、`tests/test_ipmsg_getfiledata_loopback.py`；README 同步。

## 2025/11/02 20:00 指令与信息结构优化

- 新增 `/search user:<name>|group:<name>|ip:<addr>`。
- 变更：`/info group:<name>` 现在显示“群聊历史”（聚合组内成员消息并按时间排序）。
- 移除：`/info group:` 列表语义，统一由 `/group`（无参）列出所有群组与人数。
- 文档：README 对应更新，并给出演示步骤。

## 2025/11/02 22:30 跨子网与多网卡的稳定性、诊断与易用性

- 单播发现：`/discover ip:<addr>`，用于跨子网/广播受限网络；
- 保活增强：广播后对“所有已知节点”逐个单播 keepalive，增强跨子网存在感；
- 网络诊断：`/info net` 打印当前绑定、本地广播地址、网卡与前缀；
- 运行期绑定：`/set bind <ip>`（兼容 `ip:<ip>`），设置为“用户显式绑定”，关闭后续自动切换；
- 自动选网卡（未锁定时）：收到对端报文后，若存在“同子网”的本机 IP，自动切换到该网卡（含 10s 节流）；
- 提示符体验：采用单行 `<username> =>`；
- 文件输出洁净：不再打印原始 FILE_OFFER/FILEATTACH 文本，仅显示人类可读提示；
- 启动提示：显示本机可用 IPv4 与默认下载目录绝对路径；
- 可调参数：`/set keepalive <sec>`、`/set expire <sec>`；
- 文档：README/帮助文本同步更新。

## 2025/11/02 23:10 收尾修复与兼容性

- 提示符刷新“降级为纯换行”：为兼容更老终端，移除 ANSI 清行，采用“直接换行+重绘提示符”的策略；
- rebind 后在线列表自条目清理：切换成功即移除旧 IP 的自条目，并登记新 IP，避免短时间“双自条目”。
- 下线单播：为兼容广播受限网络，`/logout`、`/exit`、EOF 退出时，除广播 `BR_EXIT` 外，会对在线表中的所有已知节点逐个单播 `BR_EXIT`，确保对方能即时更新离线状态。

—— 本阶段到此收尾。后续规划：

- 自动选网卡策略继续细化（结合默认路由/最近成功对端历史）。
- 群聊体验增强、文件目录/多文件传输、TLS/加密信道、历史持久化、可插拔 UI。
