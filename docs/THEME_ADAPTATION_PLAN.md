# 多主题适配计划（UI 主题 / 深色模式改进）

目标：逐步把主题变量集中化，支持至少 `light` 与 `dark` 两套完整变量，降低代码中硬编码颜色的数量，保证切换即时生效并向后兼容 legacy QSS。

实施步骤（建议顺序）：
1) 代码审计：收集所有硬编码颜色与 QSS 位置（已发现：`NZFeiQ/gui/*.py` 中大量 `setStyleSheet`，`NZFeiQ/gui/styles.py` 仅有占位变量，`legacy/zfeiq_gui/style.py` 有现成 QSS 模板）。
2) 主题变量：在 `NZFeiQ/gui/styles.py` 中添加 `THEMES = { 'light': {...}, 'dark': {...} }`，定义 `PRIMARY_TEXT, SECONDARY_TEXT, BACKGROUND_PANEL, BORDER, CHAT_*` 等键。
3) 主题引擎：新建 `NZFeiQ/gui/theme.py`（或在 `styles.py` 中），提供 `apply_theme(theme_code, app, bridge=None)`，负责：设置 `QPalette`（跨平台优先）并返回通用 QSS 片段供 widget 使用，同时触发 `bridge.sig_theme_changed`。
4) 渐进改造：先在关键视图（`chat.py`, `login.py`, `settings.py`, `main.py`）用变量替换硬编码颜色，优先替换背景/文本/聊天气泡颜色，保留复杂小组件的 QSS 作为过渡。
5) Settings 集成：`NZFeiQ/gui/settings.py` 已使用 `SUPPORTED_THEMES`，确保保存到 `common/config.json`（`theme` 字段）并支持即时生效（已通过 `sig_theme_changed`）。
6) Legacy QSS：在 `legacy/zfeiq_gui/style.py` 中提取可复用 QSS 模板，作为 dark/light 的参考实现或直接合并进 `theme.apply_theme` 的组合 QSS。
7) 验证与回归：测试步骤列在下方，任何涉及布局/可访问性/对比度的改动需附回归截图或录屏。

快速验证（在项目根目录运行）：
```bash
# 在配置里设置主题并重启（简单路径）
python3 -c "import json; d=json.load(open('common/config.json')); d['theme']='dark'; json.dump(d, open('common/config.json','w'), indent=2)"
python3 NZFeiQ/gui/main.py

# 或在 GUI 设置里选择 Theme -> Save（会触发 sig_theme_changed）
```

验收标准（MVP）：
- 应用可切换：从 `settings` 切换 `light`/`dark` 即时看到背景、聊天气泡、侧栏与顶部标题的明显变化。
- 变量化覆盖率：关键界面（聊天/登录/设置）不再使用硬编码颜色（≤3 处保留例外）。
- 向后兼容：legacy QSS 可作为选项载入，且不会破坏主流程。

下一步：
- 我可以生成 `NZFeiQ/gui/theme.py` 的骨架实现与一次性替换清单（按文件列出需替换的颜色字面量），并为首轮改造提交一个小 PR 草案。
- 是否需要我现在直接生成 `theme.py` 的初始实现？
