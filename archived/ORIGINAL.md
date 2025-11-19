# 本文件用于归档其他设计文件

## 附录A：需求说明原文（REQUEST.md）

```markdown
# REQUEST.md 项目需求说明文档

## 开发要求

Project3： 在瑞芯微板子 Firefly ROC-RK3566-PC 的麒麟系统 UbuntuKylin 20.04 上实现简单的局域网飞秋功能。

1. 可以建立无需服务器的聊天室,具有群聊天室的功能.  
2. 搜索用户功能，可通过输入用户名、组名、IP等来查找我的好友.  
3. 分组功能，给所有在线的用户群发消息及分组群发功能.  
4. 支持表情包发送(可自定义表情包)、截图功能。  

## 环境要求

- 板载 Python 3.8.
- WSL 中有一套 Firefly SDK，但还不会用
- Qt 版本： 5.15.0

1. 板子只有 1+8G，目前剩下 2G 存储空间
2. 开发环境：Win11 + Ubuntu WSL 20.04.5 LTS + 板卡系统 KylinOS 20.04  
3. 老师要求调用 NPU 整活

## 当前任务

实现一个基于 Python 3.8 与 IPMSG 协议的文本信息收发软件 ZFeiQ，CLI 版本。
实现 IPMSG 协议中的用户发现、信息更新和文本信息收发
字符编码：UTF-8
通信端口：2425

- 实现命令
  - /login
    - 输入 login 后要求用户输入登录用户名，无需密码  
    - 然后向局域网发送 IPMSG_BR_ENTRY，根据从其他主机得到的 IPMSG_BR_ENTRY_REPLY 更新节点列表  
  - /logout
    - 输入 logout 后弹出提示是否登出的信息，默认选项 N（不登出，保留在线）
    - 用户输入 Y 或 y 时发送 IPMSG_EXIT 给其他主机，然后退出程序
  - /discover
    - 发现局域网内的其他用户
  - /sysinfo 或 /info sys
    - 显示当前用户名，当前 IP，在线人数，在线用户列表
  - /send user:\<username\> \<text\>  
    - 以 IPMSG_SENDMSG 形式向用户 \<username\> 发送文本信息 \<text\>
  - /send ip:\<ipv4addr\> \<text\>  
    - 以 IPMSG_SENDMSG 形式向 IPv4 地址 \<ipv4addr\> 发送文本信息 \<text\>
    - 发送后该消息进入待确认队列
  - /sendall \<text\>
    - 遍历在线用户，逐个单播发送文本信息（进入待确认队列）
  - /group <group_name> -\<subcommand\> [username]
    - -add [username]：当无 username 时创建群组；有 username 时将用户加入群组
    - -delete [username]：当无 username 时删除群组；有 username 时将用户移出群组
  - /info user:\<username\>
    - 展示自上线以来双方的所有信息

- 主程序逻辑
  - 若接收到 IPMSG_BR_ENTRY_REPLY 后更新节点表
  - 若接收到 IPMSG_SENDMSG 则解包信息后立即显示源的用户名，IP 地址和文本信息内容，然后单播 IPMSG_RECVMSG 作为确认
  - 若接收到 IPMSG_RECVMSG 则对照其包编号和待确认队列的包编号，若已确认则从待确认队列中删除
  - 重传机制你看着来

## 我也是第一次实现 IPMSG 协议，如有错漏劳烦不吝赐教，谢谢

## 附录B：设计说明原文（DESIGN.md）

```markdown
# ZFeiQ CLI 设计说明

本设计实现基于 IP Messenger (IPMSG) 协议的最小可用 CLI 局域网聊天工具，重点覆盖：上线发现、节点应答、文本消息收发与确认、节点退出与在线列表维护。

## 协议子集与映射

- 传输层：UDP/IPv4，端口 2425，广播地址 255.255.255.255
- 文本编码：UTF-8
- 报文格式：`ver:packetNo:username:hostname:command:extension`，以 ASCII 冒号分隔。
  - ver 固定为 `1`
  - packetNo：毫秒时间戳+随机偏移，进程唯一
  - command：32 位整型，低 8 位为主命令，高位为选项位
  - extension：命令相关的扩展区，文本消息直接放入此区；多个字段用 `\0` 分隔

- 命令常量（与 IPMSG 保持一致命名）：
  - IPMSG_BR_ENTRY (0x00000001)：上线广播
  - IPMSG_BR_EXIT (0x00000002)：下线广播
  - IPMSG_ANSENTRY (0x00000003)：对上线广播的单播应答（注：原需求中的 "BR_ENTRY_REPLY" 对应此命令）
  - IPMSG_SENDMSG (0x00000020)：发送消息
  - IPMSG_RECVMSG (0x00000021)：消息确认
  - 发送确认选项 IPMSG_SENDCHECKOPT (0x00000100)：与 SENDMSG 叠加，要求对方回 RECVMSG

- 行为约定：
  - /login 或 /discover 发送 BR_ENTRY 广播，收到 ANSENTRY/BR_ENTRY 即更新在线表；对对方的 BR_ENTRY 必须回复 ANSENTRY
  - 收到 SENDMSG：打印消息并回 RECVMSG（extension 为被确认的 packetNo）
  - 收到 RECVMSG：根据 packetNo 移除待确认队列

## CLI 指令集

- /login：输入用户名后上线（广播 BR_ENTRY）
- /logout：确认后下线（广播 BR_EXIT）并退出
- /discover：主动发现（广播 BR_ENTRY）
- /sysinfo 或 /info sys：显示用户名、本机 IP、在线人数与列表
- /send user:\<name\> \<text\>：按用户名单播文本（SENDMSG|SENDCHECKOPT）
- /send ip:\<ipv4\> \<text\>：按 IP 单播文本（SENDMSG|SENDCHECKOPT）
- /sendall \<text\>：向所有在线用户群发（逐个单播）
- /group <group_name> -add [username]：创建群组（无用户名时）或添加成员
- /group <group_name> -delete [username]：删除群组（无用户名时）或移除成员
- /info user:\<name\>：显示与该用户会话的历史（本次运行内）

歧义处理：当用户名不唯一时，提示冲突并展示候选；需要使用 /send ip:...

## 重传策略（最小实现）

- 进入待确认队列的消息：3 秒未确认则重传，最多 3 次；超过上限标记为失败并从队列移除

## 资源占用与兼容

- 仅标准库，无第三方依赖，适配 Python 3.8
- Windows / Linux 通用，启用 UDP 广播（SO_BROADCAST），端口 2425

## 后续扩展点

- 分组与群发（按标签聚合、一次循环多播）
- 加密（libsodium + ChaCha20-Poly1305），可在 extension 里携带密文与 nonce
- 表情与文件（用 IPMSG file 相关命令或自定子协议）
- NPU demo：消息触发小推理并回传结果

```
