
# CLI 与 GUI 功能对照表（Alpha 4.2）

| 功能点/说明 | GUI支持 | CLI支持/命令 | 备注 |
|---|---|---|---|
| 登录上线 | ✅ 登录页 | `/login [username]` |  |
| 下线/退出 | ✅ 菜单/按钮 | `/logout`, `/exit` |  |
| 版本与日期 | ✅ 标题/关于 | 启动 banner |  |
| 广播发现 | ✅ 用户页“发现” | `/discover` |  |
| 单播发现（跨子网） | ✅ 信息页“Discover IP” | `/discover ip:<addr>` |  |
| 查看在线列表 | ✅ 用户/信息页 | `/info` |  |
| 查看网络信息 | ✅ 信息页 | `/info net` |  |
| 绑定本机 IP | ✅ 设置页 | `/set bind <ip>` | 多网卡支持 |
| 子网掩码设置 | ✅ 设置页 | 自动推导，仅展示 | CLI不可编辑 |
| 向用户发送 | ✅ 聊天页 | `/send user:<name> <text>` |  |
| 向 IP 发送 | ✅ 聊天页 | `/send ip:<addr> <text>` |  |
| 向群组发送 | ✅ 聊天页 | `/send group:<group> <text>`<br>`/group <g> -send <text>` | 兼容旧命令 |
| 向所有在线发送 | ✅ 聊天页 | `/send all <text>` |  |
| 编码切换 | ✅ 设置页 | `/set encoding <utf8|gbk>` |  |
| Emoji 发送 | ✅ 表情网格 | `/emote list`, `/emote send <target> <name>` |  |
| 气泡样式显示 | ✅ | ❌ | GUI专属 |
| 发送文件 | ✅ 文件块/拖拽/粘贴 | `/file send user|ip <path>` |  |
| 入站要约列表 | ✅ 聊天区卡片 | `/file list` |  |
| 接受要约 | ✅ Accept按钮 | `/file accept <id>` |  |
| 取消要约 | ✅ Cancel按钮 | `/file cancel <id>` |  |
| 下载目录 | ✅ 设置页 | 默认当前目录（GUI 可修改；程序默认映射到 `commons/downloads/`） | CLI不可配置 |
| 粘贴文件 | ✅ 文件块 | ❌ | GUI专属 |
| “文件块”合并发送 | ✅ | ❌ | GUI专属 |
| 区域截图 | ✅ 区域选择+遮罩 | `/screenshot send <target>` | CLI仅全屏，无区域选择 |
| 列出所有组与成员 | ✅ 组页 | `/group` |  |
| 添加/移除成员 | ✅ 组页按钮 | `/group <group> -add|-delete [username]` |  |
| 进入群聊 | ✅ “进入聊天” | `/send group:<group> <text>` |  |
| 新建分组 | ✅ 新建按钮 | `/group <group> -add` |  |
| 重命名分组 | ✅ 重命名按钮 | `/group <group> -rename <newname>` | CLI 支持原子重命名（新增 `-rename` 子命令） |
| 加密模式 | ✅ 安全（密钥）页 | `/set encrypt <off|on|strict>` |  |
| 密钥生成/加载 | ✅ 安全（密钥）页 | 自动生成/加载 | CLI无显式命令 |
| 指纹展示/公钥导出/重生成 | ✅ 安全（密钥）页 | ❌ | GUI专属 |
| 查看与用户历史 | ✅ 历史窗口 | `/info user:<name>` |  |
| 查看群组历史 | ✅ 聊天页聚合 | `/info group:<name>` |  |
| 搜索用户/组/IP | ✅ 搜索框 | `/search user|group|ip` |  |
| 语言切换 | ✅ 设置页（所有页面即时刷新，文本集中管理） | `/set language <zhCN|enUS>` |  |
| 侧栏间距调节 | ✅ 完全灵活 | ❌ | GUI专属 |
| 设置页控件宽度自适应 | ✅ | ❌ | GUI专属 |
| 头像预览健壮 | ✅ 仅在有效路径时显示 | ❌ | GUI专属 |
| 在线状态 | ✅ 设置页 | `/set status <...>` |  |
| Debug/Trace 日志开关 | ✅ 设置页 | `/set debug <on|off>`, `/set trace <on|off>` |  |
| Keepalive/Expire | ✅ 设置页 | `/set keepalive <sec>`, `/set expire <sec>` |  |
| 主题（深色/浅色） | ✅ 设置页 | ❌ | GUI专属 |
| 头像 | ✅ 设置页 | ❌ | GUI专属 |
| 截图/下载目录 | ✅ 设置页 | 默认当前目录（默认映射到 `commons/downloads/`） | CLI不可配置 |
| RK3566 OpenGL/Emoji回退 | ✅ | ❌ | GUI专属 |
| 多网卡自动/手动绑定 | ✅ 设置页 | `/set bind <ip>` |  |

---

## 快速命令参考（CLI）

| 功能 | 命令 |
|---|---|
| 登录/退出 | `/login [username]`，`/logout`，`/exit` |
| 发现 | `/discover`，`/discover ip:<addr>`，`/info`，`/info net` |
| 发送消息 | `/send user:<name>|ip:<addr>|group:<group>|all <text>` |
| 文件 | `/file send user|ip <path>`，`/file list`，`/file accept <id>`，`/file cancel <id>` |
| 表情 | `/emote list`，`/emote send user|ip|group|all <name>` |
| 截图 | `/screenshot send user|ip|group|all` |
| 分组 | `/group`，`/group <group> -add [username]`，`-delete [username]` |
| 设置 | `/set language|status|debug|trace|encoding|keepalive|expire|bind|encrypt <value>` |

> 说明：GUI 的“文件块”、气泡样式、主题/头像、区域截图选择器等为 GUI 专属交互；CLI 保留核心协议和自动化能力，优先保证在纯文本环境的易用性。

### 注记（安全/密钥）

- “刷新指纹”按钮已移除：重生成密钥后指纹会自动更新，无需手动刷新。
- 指纹显示采用 16‑bit 分组（每 4 个十六进制字符为一组），并使用等宽小号字体以提升可读性。
