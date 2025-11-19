# CLI 与 GUI 功能对照表（Alpha 3.4）

本文汇总当前 GUI 端可见的功能点，并逐项标注 CLI 是否具备等效能力或替代方式，便于选择使用形态与编写自动化脚本。

术语说明：

- 支持：CLI 提供直接等效命令或行为
- 部分支持：CLI 有替代/近似能力，但与 GUI 交互方式不同或存在限制
- GUI 专属：仅 GUI 存在的交互/视觉能力，CLI 无对应
- N/A：不适用（UI 呈现相关）

---

## 账号 / 会话

- 登录上线：支持（GUI 登录页；CLI `/login [username]`）
- 下线/退出：支持（GUI 菜单/按钮；CLI `/logout`, `/exit`）
- 版本与日期：支持（GUI 标题/关于；CLI 启动 banner 显示版本与日期）

## 发现 / 在线列表 / 网络

- 广播发现：支持（GUI 用户页“发现”；CLI `/discover`）
- 单播发现（跨子网）：支持（GUI 信息页“Discover IP”; CLI `/discover ip:<addr>`）
- 查看在线列表：支持（GUI 用户/信息页；CLI `/info`）
- 查看网络信息（绑定 IP、广播、网卡）：支持（GUI 信息页；CLI `/info net`）
- 绑定本机 IP（多网卡）：支持（GUI 设置“网卡 IP/绑定 IP”；CLI `/set bind <ip>`）
- 子网掩码设置：部分支持（GUI 可显示/编辑；CLI 不提供显式设置，自动推导，仅信息展示）

## 消息 / 聊天

- 向用户发送：支持（GUI 选择用户进入聊天；CLI `/send user:<name> <text>`）
- 向 IP 发送：支持（GUI 选择节点；CLI `/send ip:<addr> <text>`）
- 向群组发送：支持（GUI 进入群聊；CLI `/send group:<group> <text>` 或 `/group <g> -send <text>` 兼容）
- 向所有在线发送：支持（GUI 目标 `all`；CLI `/send all <text>`）
- 编码切换（UTF-8/GBK）：支持（GUI 设置；CLI `/set encoding <utf8|gbk>`）
- Emoji 发送：支持（GUI 表情网格插入文本；CLI `/emote list`, `/emote send <target> <name>`）
- 气泡样式显示：GUI 专属（CLI 纯文本）

## 文件传输（IPMSG 附件 + 2425/TCP GETFILEDATA）

- 发送文件：支持（GUI 选取/拖拽/粘贴“文件块”；CLI `/file send user|ip <path>`）
- 入站要约列表：支持（GUI 聊天区内嵌要约卡片；CLI `/file list`）
- 接受要约：支持（GUI “Accept”；CLI `/file accept <id>`）
- 取消要约：支持（GUI “Cancel”；CLI `/file cancel <id>`）
- 下载目录：部分支持（GUI 可在设置中指定下载目录；CLI 默认保存到当前工作目录，不提供显式 `/set download_dir`）
- 粘贴文件：GUI 专属（CLI 通过显式路径发送）
- “文件块”合并发送：GUI 专属（CLI 按命令逐条发送）

## 截图 / 图片

- 区域截图（暗色遮罩 + 5px 边框）并发送：部分支持（GUI 支持区域选择；CLI 支持全屏截图并通过临时 BMP `/screenshot send <target>`，不提供区域选择 UI）

## 分组管理

- 列出所有组与成员数量：支持（GUI 组页；CLI `/group`）
- 添加/移除成员：支持（GUI 组页按钮；CLI `/group <group> -add|-delete [username]`）
- 进入群聊：支持（GUI “进入聊天”；CLI 通过 `/send group:<group> <text>` 直接发送）
- 新建分组：支持（GUI 新建；CLI `/group <group> -add` 可创建空组）
- 重命名分组：部分支持（GUI 提供“重命名”（内部为新建+迁移+删除旧组）；CLI 无直接 rename，可手动新建新组、逐个 `-add` 迁移成员后删除旧组）

## 加密 / 密钥

- 加密模式（off/on/strict）：支持（GUI 密钥页；CLI `/set encrypt <off|on|strict>`）
- 密钥生成/加载：支持（GUI 提供 UI；CLI 在启用 on/strict 时自动 `_ensure_keys()`，失败则回退 off）
- 指纹展示、公钥导出、重生成：部分支持（GUI 有可视化与导出；CLI 无显式导出/重生成命令）

## 历史 / 搜索

- 查看与用户历史：支持（GUI 历史窗口；CLI `/info user:<name>`）
- 查看群组历史：支持（GUI 聊天页聚合；CLI `/info group:<name>`）
- 搜索用户/组/IP：支持（GUI 用户/组页搜索框；CLI `/search user|group|ip`）

## 设置 / 偏好

- 语言切换：支持（GUI 设置；CLI `/set language <zhCN|enUS>`）
- 在线状态（online/busy/away）：支持（GUI 设置；CLI `/set status <...>`）
- Debug/Trace 日志开关：支持（GUI 设置；CLI `/set debug <on|off>`, `/set trace <on|off>`）
- Keepalive/Expire：支持（GUI 设置；CLI `/set keepalive <sec>`, `/set expire <sec>`）
- 主题（深色/浅色）：GUI 专属（CLI 不适用）
- 头像：GUI 专属（CLI 不适用）
- 截图与下载目录：部分支持（GUI 可在设置中配置；CLI 截图使用临时文件并删除，下载固定为当前目录）

## 其他 / 平台适配

- RK3566 软件 OpenGL 回退、Emoji 字体回退：GUI 专属（渲染与字体加载相关）
- 多网卡自动/手动绑定：支持（GUI 可视化；CLI `/set bind <ip>` 与自动切换策略）

---

## 快速命令参考（CLI）

- 登录/退出：`/login [username]`，`/logout`，`/exit`
- 发现：`/discover`，`/discover ip:<addr>`，`/info`，`/info net`
- 发送消息：`/send user:<name>|ip:<addr>|group:<group>|all <text>`
- 文件：`/file send user|ip <path>`，`/file list`，`/file accept <id>`，`/file cancel <id>`
- 表情：`/emote list`，`/emote send user|ip|group|all <name>`
- 截图：`/screenshot send user|ip|group|all`
- 分组：`/group`，`/group <group> -add [username]`，`-delete [username]`
- 设置：`/set language|status|debug|trace|encoding|keepalive|expire|bind|encrypt <value>`

> 说明：GUI 的“文件块”、气泡样式、主题/头像、区域截图选择器等为 GUI 专属交互；CLI 保留核心协议和自动化能力，优先保证在纯文本环境的易用性。
