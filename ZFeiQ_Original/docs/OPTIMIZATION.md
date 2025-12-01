# ZFeiQ 优化建议（RK3566 / Linux 侧重点）

本文汇总近期可落地的性能与体验优化方向，按模块分类列出要点与取舍。建议先做“低风险、高收益”的条目，并结合现有测试脚本验证。

## 传输与协议
- 加密会话优先：默认开启 `encrypt=on` 并优先走 `ENC2`，减少每条消息 RSA-OAEP 包裹的开销。
- 握手竞态消解：同时 KX1 的情况以指纹字典序选主，从属方复用既有会话，避免重复派生与抖动。
- 重放窗口尺寸：根据实际消息频率调整为 512~2048；滑动窗口用 deque + set，定期裁剪过期计数。
- 会话过期策略：不活跃 30 分钟或单向计数达到 10k 触发重键；在 `_maint_loop` 中统一检查并日志提示。
- 解码容错最小化：接收端保持 utf-8→gbk→cp936→latin-1 级联，但发送端强制使用 utf-8，减少转码与兼容路径分支。

## GUI 渲染与交互
- 列表项绘制：用户列表与组列表改为“轻富文本 + 简委托”避免复杂 QStyledItemDelegate；现已统一为 Emoji 状态灯，减少重绘开销。
- 头部稳定性：登录/刷新不覆盖聊天目标头部（改为次行“我：…”显示），避免 UI 抖动与不必要的 layout thrash。
- 异步信号限流：高频刷新（如 3s 定时器）中合并 UI 更新；若数据未变化不重建列表。
- 文案集中管理：所有新增字符串进入 `lang.py`，减少界面硬编码导致的查找与维护成本。

### 禁用设置页面子选项卡切换动画（RK3566 建议）

当前 `SettingsPage` 使用 `QTabWidget`，未显式启用任何过渡/动画；在低功耗设备上仍建议确保“瞬时切换、最少重绘”，并在全局禁用 Qt 的 UI 动画以避免样式插件的潜在开销。

落地方案：

- 在应用初始化（如 `zfeiq_gui/app.py` 的 `launch_gui()` 里）增加全局 UI 动画关闭（如平台支持）：

  ```python
  from PyQt5 import QtCore, QtWidgets

  def _disable_ui_animations():
	  try:
		  # 部分平台/样式支持以下开关（Qt::UIEffect）；不支持的平台会被忽略
		  for eff in (
			  QtCore.Qt.UI_AnimateMenu,
			  QtCore.Qt.UI_AnimateCombo,
			  QtCore.Qt.UI_AnimateTooltip,
			  QtCore.Qt.UI_FadeMenu,
			  QtCore.Qt.UI_FadeTooltip,
		  ):
			  try:
				  QtWidgets.QApplication.setEffectEnabled(eff, False)
			  except Exception:
				  pass
	  except Exception:
		  pass
  ```

- 在 `SettingsPage` 构建后确保选项卡切换“即时”且避免滚动按钮与重排：

  ```python
  tabs = QtWidgets.QTabWidget()
  tabs.setUsesScrollButtons(False)       # 关闭滚动按钮，避免额外绘制
  tabs.setMovable(False)                 # 禁止拖动，减少 hover/drag 处理
  tabs.setTabBarAutoHide(True)           # 标签少时隐藏 TabBar，减少渲染
  # 若使用 QToolBox，启用：toolbox.setAnimated(False)
  ```

- 切换过程“无动画”的代码约定：如后续引入 `QStackedWidget` 的过渡封装（例如淡入淡出/滑动），统一通过配置开关屏蔽：

  ```python
  ANIMATIONS_ENABLED = False  # 全局/配置开关（设置页也可暴露）
  if not ANIMATIONS_ENABLED:
	  # 直接 setCurrentIndex，不走 QPropertyAnimation/QGraphicsEffect
	  stacked.setCurrentIndex(target)
  else:
	  # 仅在桌面/性能充足时启用动画
	  run_slide_or_fade_animation(stacked, target)
  ```

- 语言应用时减少重绘抖动：

  ```python
  self.setUpdatesEnabled(False)
  self.blockSignals(True)
  try:
	  self.apply_language(t)
  finally:
	  self.blockSignals(False)
	  self.setUpdatesEnabled(True)
  ```

验证要点：

- 切换 `SettingsPage` 子标签时 CPU 峰值降低、帧丢失现象减少；
- `QTabWidget` 不产生滚动按钮/渐隐特效；
- 在 RK3566 上全局动画关闭不会影响核心交互（菜单/下拉/提示）。

## 密钥与加密
- HKDF 统一：仅使用 HKDF-SHA256 派生 32B 会话密钥，AES-256-GCM；避免多实现分歧。
- Nonce 派生：`nonce = H(sid||dir||ctr)[0:12]`，计数单调递增确保唯一；遇到冲突立即重键并报警。
- RSA 操作收敛：会话建立后仅在重键或首次握手使用 RSA；常规消息不再做 RSA 包裹。
- 指纹 pinning：首次见面提示并持久化指纹，后续指纹变更弹窗确认，降低 MITM 风险（后续可加签名增强）。

## Python 运行时与 IO
- 文件传输：TCP 端口仍用 2425，避免 NAT/防火墙问题；读写采用块大小 64KB 并在 GUI 侧限流进度更新频率。
- 历史写入：历史文件采用独立小文件 + 原子替换，内存仅保留最后 200 条；减少频繁 JSON dump 的成本。
- 线程模型：下载与耗时操作使用 `threading.Thread`，避免 QThread 在主线程执行的陷阱；统一传入 stop_event 以支持取消。
- 路径标准化：GUI 层保存路径统一正斜杠，减少跨平台路径错误与重复 `ensure_dir` 调用的开销。

## RK3566/AArch64 细节
- OpenGL 回退：在检测到 RK3566/软 OpenGL 场景时强制软件渲染（已有逻辑），避免 GPU 不稳定导致的 UI 卡顿与崩溃。
- 加密库选择：优先 `cryptography`，不在 RKNN 场景加载重型依赖；确保 `PyCryptodome` 仅为后备路径。
- OCR 与 NPU：OCR 页独立弹窗，按需加载，避免主界面启动时初始化 RKNN；所有 NPU 依赖与模型文件保留在 Archived/ 下。

## 测试与监控
- 冒烟用例：维护 `tests/test_key_exchange_smoke.py` 验证 KX/ENC2 洁净路径；加入计数窗口与过期会话的断言。
- 在环脚本：利用 `tests/discover_and_sendall.py` 与 `tests/group_send_demo.py` 做真实网络与组播验证。
- 日志与指标：CLI 侧增加轻量计时日志（握手耗时、消息加解密耗时均值/分位），仅在 debug/trace 开启时打印。

## 后续演进（可选）
- PFS：迁移到 X25519-ECDH 临时密钥协商，并用静态 RSA 对握手材料签名；现阶段以 Level B 为主、保持回退兼容。
- UI 委托优化：若需要更强的右对齐与单元格布局，可引入轻量委托渲染（仅对 LOCAL 行与组头应用），谨慎评估复杂度。
- 持久化压缩：历史与状态文件在达到一定大小后按日期滚动与压缩，避免长时间运行的膨胀。

——

实施顺序建议：
1) 会话过期/重键与重放窗口裁剪（传输层）。
2) GUI 刷新限流与稳定性收敛（交互层）。
3) 指纹 pinning + 异常提示（安全与体验）。
4) 在环基准与指标打印（测试与监控）。
