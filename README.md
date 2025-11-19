# ZFeiQ（IPMSG/飞秋 互通 · CLI + GUI） — Alpha 3.4

ZFeiQ 是一个基于 Python 的局域网即时通信工具，兼容飞秋/IPMSG 协议要点（BR_ENTRY/ANSENTRY/BR_EXIT/ABSECE、SENDMSG/RECVMSG、FILEATTACH/GETFILEDATA 等）。

提供两种形态：

- CLI：轻量、纯标准库实现核心协议与指令；可脚本化
- GUI：PyQt5 现代化界面，登录页 IP 选择、分组与私聊、表情/截图、文件要约接收、加密模式管理、主题与语言、截图与下载目录配置

> 适配 Windows / Linux / aarch64（RK3566 等）。

---

## 功能总览（Alpha 3.4 更新）

- 互通协议：上线/应答/离线、文本消息、在线发现、附件式文件传输（GETFILEDATA 拉取）、RELEASEFILES
- 多网卡/多子网：自动选择网卡；支持锁定绑定 IP；支持单播发现；设置页可配置子网掩码（用于广播地址计算）
- 聊天体验（GUI）：
  - 登录页：用户名输入 + 本机 IP 下拉选择；Enter 快捷登录
  - 聊天页：移除冗余顶部目标下拉；采用用户/组页入口；消息标签按用户拆分 + “全部”汇总；Enter 发送（Shift+Enter 换行）
  - 本地用户信息：两行显示（用户名 + 在线状态 / 下方 IP），动态刷新；发送区不再重复显示 `[LOCAL]`
  - 气泡样式：本地消息右对齐绿色气泡，对端消息左对齐白色气泡，包含用户名与 IP，区分更清晰
  - 表情/截图：Emoji 网格弹窗（约 100 个常用表情）；区域截图带暗色遮罩与 5px 边框；截图目录可配置
  - 编码提示：发送区显示当前编码；“编码自检”(Encoding Self-Test) 按钮发送多语言+Emoji 测试
  - 文件：已内嵌聊天区（不再单独“文件”页面）；展示 用户名[IP:...] 文件名 时间/大小/来源；Accept/Cancel 链接操作；接收进度与保存完成提示；发送侧采用“文件块”插入（支持 Backspace 删除，Enter 一键发送）；粘贴文件加入文件块统一发送；完成后保持在聊天页
  - 分组：左侧分组列表（显示组名与成员数），右侧成员列表与“添加/移除成员”“进入聊天”；支持“新建分组（New Group N）”“重命名”；支持组名/成员模糊搜索
  - 在线统计：用户页 / 信息页 显示在线节点计数
  - 主题/语言：深色/浅色；中英双语切换（Settings/所有按钮、占位符与标签已全面适配）
  - 状态：online/busy/away 显示在用户信息区
  - 平台 & 架构检测：Windows 11 / Linux aarch64 等
  - RK3566 适配：自动启用软件 OpenGL、Emoji 字体加载与本地 ./fonts 目录回退
- 加密：RSA-3072 + AES-256-GCM 混合；模式 off/on/strict；指纹展示；一键重生成与公钥导出；严格模式缺少对端公钥时拒绝发送
- 历史：基于 ip:/group:/all/显示名[IP:...] 目标聚合；GUI 历史对话框可查看
- 持久化：语言/状态/编码/主题/绑定 IP/下载目录/截图目录/头像/加密模式 保存在 `zfeiq_state.json`
- CLI 能力：
  - 登录/退出、在线发现/诊断、私聊/群发、分组管理、文件要约收发、可调保活/过期
  - 运行期绑定 `/set bind <ip>`，快速切换生效

---

## 环境要求


 依赖：建议安装 `cryptography`（首选）或 `pycryptodome`（后备）。

### 安装依赖

使用已配置的 Python 环境安装：

 ```pwsh
pip install -r requirements.txt
 ```

本项目的 `zfeiq_cli/crypto.py` 会优先使用 `cryptography`，若不可用则自动回退使用 `pycryptodome`。

```pwsh
pip install "PyQt5==5.15.0"
```

---

## 快速开始

GUI 启动（推荐）：

```pwsh
python .\main.py --gui
```

CLI 启动：

```pwsh
python .\main.py              # 默认 UDP/2425；自动选网卡
python .\main.py --port 2426  # 自定义端口
python .\main.py --bind 192.168.1.100  # 指定绑定 IP（通常不需要）
```

> Windows 防火墙请允许专用网络 UDP；如端口被占用，改用其它端口或关闭占用程序。

---

## GUI 使用说明（核心交互）

1. 登录页：用户名 + IP 下拉；Enter 登录；成功后显示左侧导航。
2. 用户页 / 组页：选择聊天对象并自动切换到聊天页；显示在线计数与分组成员数量。
3. 聊天页：
   - 顶部头像区：用户名(加粗) + 状态；下方 IP；本地消息绿色高亮。
   - 输入框：Enter 发送，Shift+Enter 换行；Emoji / 表情管理 / 截图 / 常用语 / 历史 / 发送文件 按钮。
   - 截图：区域拖拽后弹确认对话框（发送 / 保存 / 保留）。
4. 文件（内嵌聊天）：入站文件要约以消息形式出现，含 Accept/Cancel 链接；点击 Accept 后显示实时进度与保存完成提示；支持在输入框 Ctrl+V 粘贴文件，加入“文件块”统一发送。
5. 信息页：本机网络信息、在线节点列表与数量、定向/广播发现。
6. 密钥页：加密模式切换、指纹刷新、重生成、导出公钥。
7. 设置页：语言 / 状态 / 编码 / 主题 / 网卡 IP / 绑定 IP / 子网掩码 / 下载 & 截图目录 / 头像 / Keepalive / Expire / 日志开关；自动同步当前配置。

---

## CLI 常用命令（精要）

- 账号：`/login [name]`、`/logout`、`/exit`
- 发现：`/discover`、`/discover ip:<addr>`、`/info`、`/info net`
- 查询：`/search user|group|ip`、`/info user:<name>`、`/info group:<name>`、`/group`
- 发送：`/send user:<name>|ip:<addr>|group:<group>|all <text>`
- 分组：`/group <group> -add|-delete [username]`
- 文件：`/file send user|ip <path>`、`/file list`、`/file accept <id>`、`/file cancel <id>`
- 设置：`/set language|status|debug|trace|encoding|keepalive|expire|bind <val>`、`/clear`

---

## 文件与加密说明

### 文件

- 默认采用 IPMSG 附件（FILEATTACH）+ 2425/TCP GETFILEDATA 方式；接收后自动发送 RELEASEFILES
- GUI 以要约消息形式展示，可 Accept/Cancel；下载目录在“设置”页设定（不再有单独文件页）；发送文件采用“文件块”统一发送流程
- 兼容旧式一次性直连要约（自建临时 TCP 服务器）

### 加密

- 混合加密：RSA-3072 OAEP-SHA256 包裹 AES-256-GCM 会话密钥
- 发送路径：若 on/strict 模式且已有对端公钥，则加密文本；否则 strict 模式下拒绝发送并主动请求公钥
- 指纹：SHA-256(pubkey) 十六进制两字符分组显示；便于比对
- 模式：off（明文）/ on（有公钥则加密）/ strict（无公钥不发送）

---

## 故障排查

- 无法发现对端：确认端口一致（默认 2425）、同一二层网、允许 UDP/广播；跨子网请使用单播发现
- 多网卡切换：通常不必绑定；必要时在 GUI 设置“网卡 IP”或 CLI `/set bind <ip>`
- 端口占用：Windows 出现 `[WinError 10013]` 可更换端口或关闭占用程序

---

## 开发与目录结构

```text
ZFeiQ/
  main.py                # 入口；--gui 启动 GUI，否则启动 CLI
  zfeiq_cli/             # CLI 实现（传输/协议/文件等）
  zfeiq_gui/             # GUI（PyQt5）
    main_window.py       # 主窗体与各页面
    backend.py           # GUI 后端桥接 CLI 能力
    app.py, __init__.py  # 启动封装
  tests/                 # 一些快速检查与演示脚本
```

建议在 Windows PowerShell/Conda 环境中运行；Linux/aarch64 需要合适的 Python 与 PyQt5。

---

## 项目背景

在瑞芯微板子麒麟系统实现简单的局域网飞秋功能。

1. 可以建立无需服务器的聊天室,具有群聊天室的功能.
2. 搜索用户功能，可通过输入用户名、组名、IP 等来查找我的好友.
3. 分组功能，给所有在线的用户群发消息及分组群发功能.
4. 支持表情包发送(可自定义表情包)、截图功能。
5. 调用 RK3566 的 NPU，实现典型边缘 AI 智能的加速功能。考虑调用 RK3566 的 NPU 实现根据文字信息自动推荐表情包，但需要评估
6. 加密通讯（自己想做的）

---

## 版权与协议

本项目用于学习与交流，遵循相关协议与当地法律法规；请合理使用，勿用于任何违法场景。

欢迎提交 Issue / PR 反馈互通与功能优化建议。

