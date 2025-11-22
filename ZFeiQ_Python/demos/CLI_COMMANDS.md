ZFeiQ CLI — 常用命令与运行说明

概述
- 所有 CLI 演示脚本均放在本目录 `demos/`。
- 使用 `run_cli_repl.py` 启动交互式 CLI（或用 `run_cli_repl.ps1` 在 PowerShell 下启动）。

运行（PowerShell）：
```powershell
# 进入仓库根或 demos 目录，然后：
$env:PYTHONPATH='e:\Main\JuniorI\Course_Linux_RK3566\ZFeiQ\ZFeiQ_Python'
python e:\Main\JuniorI\Course_Linux_RK3566\ZFeiQ\ZFeiQ_Python\demos\run_cli_repl.py
```
或双击 `run_cli_repl.ps1`（右键以 PowerShell 运行）。

快速命令参考（在 REPL 中输入）：
- `help`                   - 显示帮助文本
- `discover`               - 发送广播发现包
- `send <target> <text>`   - 发送文本到目标（使用 `all` 广播）
- `group <name> -add <u>`  - 添加群组成员
- `group <name> -send <text>` - 向群组发送消息
- `file send <target> <path>` - 发送文件要约
- `file list`              - 列出待处理的文件要约
- `file accept <id> [ip] [dst]` - 接受文件要约
- `file cancel <id>`       - 取消/注销映射
- `set download_dir <path>` - 设置默认下载路径
- `set bind <ip>` / `set bind unlock` - 用户绑定或解锁自动切换
- `info` / `info net`      - 系统/网络信息
- `search user:<name>` / `search ip:<addr>` - 历史搜索
- `clear`                  - 打印空行（清屏替代）
- `logout` / `exit`        - 注销并退出 REPL

注意
- 所有演示与测试脚本均应放在 `demos/` 或 `tests/`，不要仅在 PowerShell 中复制粘贴单行 Python。
- 若在嵌入式设备（如 RK3566）部署，请先验证依赖安装，某些包可能需要交叉编译或预编译 wheel。