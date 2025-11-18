# ZFeiQ CLI（IPMSG 兼容子集）

一个轻量、纯标准库的“飞秋”命令行实现（Python 3.8+），支持与飞秋/IPMSG 的基础互通：上线/离线、文本消息、在线发现、附件式文件互传等。

## 亮点

- 互通：兼容 BR_ENTRY/ANSENTRY/BR_EXIT/BR_ABSENCE、SENDMSG/RECVMSG；FILEATTACH/GETFILEDATA 基础互传
- 体验：单行提示“&lt;username&gt; =>”；外部事件到来时自动换行并重绘提示符（兼容老终端）
- 多网卡：自动选择本地网卡；运行期 `/set bind <ip>`（兼容 `ip:<ip>`）锁定绑定；未锁定时可“同子网自动切换”
- 跨子网：`/discover ip:<addr>` 单播发现；保活时对已知节点单播 keepalive；`/info net` 网络诊断
- 稳定：送达确认与自动重传（仅对声明 cap=ack 的对端请求回执）；可调保活/过期（`/set keepalive|expire`）

## 快速开始（PowerShell / Linux）

```powershell
cd e:\Main\JuniorI\Course_Linux_RK3566\CLI251101
python .\main.py   # 默认 UDP/2425；自动选网卡；防火墙请允许专用网络 UDP
```

常见参数：

- 端口：`python .\main.py --port 2426`
- 启动绑定：`python .\main.py --bind 192.168.137.1`（一般不必用）

## 常用命令（精要）

- 账号：`/login [name]`、`/logout`、`/exit`
- 发现：`/discover`、`/discover ip:<addr>`、`/info`、`/info net`
- 查询：`/search user|group|ip`、`/info user:<name>`、`/info group:<name>`、`/group`（列出组）
- 发送：`/send user:<name>|ip:<addr>|group:<group>|all <text>`
- 分组：`/group <group> -add| -delete [username]`（兼容 `-send <text>`）
- 文件：`/file send user|ip <path>`、`/file list`、`/file accept <id>`、`/file cancel <id>`
- 设置：`/set language|status|debug|trace|encoding|keepalive|expire|bind <val>`、`/clear`

提示：启动时会打印本机 IPv4 列表与默认下载目录；`/set bind ip:<addr>` 与 `/set bind <addr>` 等价。

## 文件互通（概要）

- 本实现之间：基于 `FILE_OFFER` 的一次性 TCP 端口直传
- 与飞秋/IPMSG：发送端随 `SENDMSG` 携带 FILEATTACH；接收端用 2425/TCP `GETFILEDATA` 拉取
- 接收：`/file list` 查看要约；`/file accept <id>` 保存到下载目录（可设置 `/set download_dir`）

## 故障排查（速查）

- 看不到对端：检查端口一致（默认 2425）、防火墙允许 UDP/广播、是否同一二层网；跨子网用 `/discover ip:<addr>`
- 多网卡困扰：通常无需 `--bind`；必要时运行期 `/set bind <ip>` 锁定；`/info net` 查看绑定与广播地址
- 端口占用：Windows 报 `[WinError 10013]` → 关闭占用或更换端口；也可用“Windows + WSL”双端避免冲突

## 限制与规划

- 当前以文本消息为主（表情/富文本/加密待扩展）
- GETLIST/ANSLIST 仅用于同实现间共享在线列表
- 路线图：更完善的群聊、目录/多文件传输、TLS/加密、历史持久化、UI 插件化
