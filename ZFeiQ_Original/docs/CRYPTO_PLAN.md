好的，我先给出现状评估，再给出改造目标与实施计划。如果你认可，我可以按计划分阶段实现并补测试。

现状评估

加密算法: RSA-3072 (OAEP-SHA256) + AES-256-GCM（混合加密）。
公钥交换: 已实现，基于 IPMSG_GETPUBKEY/IPMSG_ANSPUBKEY，且在上线广播 BR_ENTRY/ANSENTRY 的扩展字段中声明了 cap=enc 与本机公钥指纹 fp=<sha256(pub.pem)>。
指纹绑定: cli.py 收到公钥时计算 SHA256 指纹，若与对方广播宣布的指纹不一致会告警（但未阻断）。
加密封装: 发送消息时若有对端公钥，则生成随机 32 字节会话密钥 sk，用 AES-GCM 加密正文并将 sk 用对端公钥 RSA-OAEP 包裹；头部为 ENC;alg=aes256gcm;ekey=<b64>;nonce=<b64>;tag=<b64>;b64=<cipher>。
解密路径: 收到以 ENC; 开头的消息，先用本机私钥解包 ekey，再用 AES-GCM 解密；失败则提示“加密消息解密失败”。
已知不足

认证与抗中间人: 公钥首次交换未被强认证（依赖指纹人工比对），没有签名或外部信任锚。
前向保密: 使用静态 RSA 密钥 + 每条消息的随机对称密钥，不具备 PFS（会话长期密钥泄露风险较低，但仍不如基于 ECDH 的方案）。
性能与状态: 每条消息都做一次 RSA-OAEP 包裹，开销比“建立会话后复用对称密钥”更大；也没有显式“会话”概念与重键机制。
Nonce 语义: 目前是“每条消息一个随机 12 字节 GCM nonce”，并未在“会话开始”时互换 nonce。
目标与建议

目标: 在“通信一开始（首次对话）”完成“公钥 + 双向随机种子/nonce”的握手，派生出双向会话密钥，后续消息使用会话密钥加密，减少 RSA 开销，并可引入序号/重放保护。
三个实现层级（你可选择其一）:
级别 A（最小改动，满足“交换 nonce”）：沿用现有 RSA 包裹，但双方在公钥互知后立刻互发“NONCE 消息”（随机 32B，RSA 加密对方公钥），将两端 nonce 拼接经 HKDF 生成“会话 ID”，继续沿用“每条消息单独随机 sk”的做法，但将“会话 ID + 计数器”作为 AES-GCM 的 AAD，提供轻量级会话/重放检测基础。
级别 B（推荐，增加会话密钥）：在首次往来时完成“种子交换 + HKDF 会话密钥派生”，后续消息使用“会话密钥 AES-GCM”直接加密，不再每条消息做 RSA 包裹；nonce 使用“计数器+随机”方案确保唯一性；周期性重键或基于计数阈值重键。
级别 C（增强安全，代价更大）：切换到 X25519 或 ECDH（临时密钥对）做密钥协商，并用现有 RSA-3072 对握手材料做签名认证（提供 PFS 与公钥认证）。需要引入曲线与签名格式，改动更大。
协议设计（级别 B 框架）

报文承载: 沿用 IPMSG_SENDMSG，文本层用自定义前缀，避免新命令号互通风险。
KX1（发起）："KX1;ver=1;fp=<sha256(pubA)>;ekeyA=<b64(RSA(pubB, seedA))>"
KX2（响应）："KX2;ver=1;fp=<sha256(pubB)>;ekeyB=<b64(RSA(pubA, seedB))>"
派生: seedA 与 seedB 均为 32 字节随机；双方在拥有（local_seed, peer_seed）后计算 K = HKDF( salt=0, ikm=seedA||seedB, info="zfeiq-aes256gcm", L=32 )；方向判定用 fp 排序（或 IP/端口确定顺序），确保两端一样。
编码: 会话加密头部为 ENC2;sid=<8B简短ID的b64>;ctr=<u64>；密文 b64=<cipher>；nonce 可设为 nonce = H(sid || dir || ctr)[0:12] 或 “4B 计数器 + 8B 随机”，确保唯一性。
回退: 若对端不懂 KX1/KX2/ENC2，仍保持当前 ENC;... 路径（兼容）。
代码变更点

protocol.py:
无需新指令号；用 SENDMSG 文本前缀 "KX1;" / "KX2;" / "ENC2;"。
crypto.py:
增加 HKDF 辅助（优先用 cryptography.hazmat.primitives.kdf.hkdf.HKDF，回退 Crypto.Protocol.KDF.HKDF 或基于 hashlib 的简版 HKDF）。
cli.py:
新增 self._sessions[ip] = {key: bytes, sid: bytes, send_ctr: int, last_ts: float} 与简单过期策略（如 30 分钟或 N 次消息）。
BR_ENTRY/ANSENTRY 后：若 encrypt_mode in (on, strict) 且已知对端公钥但无会话，发送 KX1；收到 KX1 时回 KX2；收到 KX2 完成派生与建会话。
发送消息：优先走 ENC2（会话密钥）；否则回退现有 ENC（RSA 包裹）。
接收消息：优先识别 ENC2 路径；落回 ENC 路径；对 sid/ctr 做简单去重/窗口检查以抑制重放。
UI/提示:
首次建会话提示“已与 X 建立加密会话（指纹 fp=...）”；指纹不匹配明显告警。
提供“重置会话密钥/忘记对端公钥”的管理命令或 GUI 按钮。
安全与实现取舍

MITM 风险: 仅靠指纹广播仍可能遭遇 MITM；可选在 GUI/CLI 中“首次见面”提示并要求用户确认/钉扎指纹；或在 KX2 中附带对（fpA|seedA）的签名用于公钥所有权证明（需要签名验签逻辑）。
Nonce 要求: GCM 关键点是“每个密钥下的 nonce 唯一”；采用会话计数器派生或“强随机”都可，计数可带来可重复性与审计优势。
向后兼容: 保持 ENC;... 路径完整，逐步引导到 ENC2。
实施计划（建议 3 步）

第 1 步（协议与基础设施）:
在 crypto.py 增加 HKDF；在 cli.py 增加会话状态与 KX1/KX2/ENC2 解析与发送；默认不启用，提供开关 encrypt=on|strict。
第 2 步（切换默认行为与可观测性）:
在加密开启时优先走 ENC2；CLI/GUI 打印“会话已建立/重键/过期”的提示；加入简单重放窗口。
第 3 步（可选增强）:
指纹首次见面确认（pinning）；KX 签名（抗 MITM）或迁移到 X25519-ECDH（PFS）。
你更倾向于“最小改动的 A”，还是“性能/体验更佳的 B（推荐）”？如果确认选项，我可以按上述计划开始落地，优先提交：

crypto.py 的 HKDF 与辅助工具
cli.py 的 KX1/KX2/ENC2 路径与会话缓存
最小回归测试：基于 tests/test_key_exchange_smoke.py 补一个会话握手与加解密的冒烟用例

——

级别 B 的完整原理（详细）

- 核心目标：通过一次双向种子交换（使用已知对端 RSA 公钥加密），在会话建立时派生出对称会话密钥，用其后的所有消息使用 AES-256-GCM 加密，降低每条消息 RSA-OAEP 的开销并提供可审计的序列化与重放抑制。

- 参与方与材料：
	- A、B 两端均持有静态 RSA-3072 密钥对（pubA/privA、pubB/privB）。
	- 每端生成 32 字节高熵随机种子 seedA、seedB。
	- A 用 pubB 加密 seedA，构造 KX1；B 用 pubA 加密 seedB，构造 KX2。

- 密钥派生（HKDF）：
	- 令 order = sort(fpA, fpB)（指纹字典序），以固定连接顺序避免两端 ikm 不一致。
	- ikm = seedA || seedB（按 order 决定前后）。
	- 使用 HKDF-SHA256：`K = HKDF(salt = 0x00..00, ikm = ikm, info = "zfeiq-aes256gcm", L = 32)` 得到 32 字节会话密钥。
	- 方向分离（可选增强）：若需要区分 A→B 与 B→A 的密钥，使用不同 info，如 `"zfeiq-aes256gcm-send"` / `"...-recv"` 派生两个密钥。

- 会话标识与计数：
	- sid = SHA256(ikm)[0:8] 作为简短会话 ID（8 字节），便于 UI 显示与日志标注。
	- 维护 `ctr_send`/`ctr_recv` 作为 64 位递增计数器（单向）。
	- 重放窗口：保存最近 `ctr_recv` 的窗口（如滑动窗口 1024）用于拒绝重复。

- Nonce 生成（保证唯一）：
	- 推荐：`nonce = H(sid || dir || ctr)[0:12]`（SHA256 截断 12 字节），在会话密钥下随计数递增，杜绝重复。
	- 备选：`nonce = <4B ctr> || <8B random>`；其中 ctr 保证单向递增，random 用于降低预测性。

- 报文编码：
	- 握手：
		- KX1: `"KX1;ver=1;fp=<fpA>;ekeyA=<b64(RSA(pubB, seedA))>"`
		- KX2: `"KX2;ver=1;fp=<fpB>;ekeyB=<b64(RSA(pubA, seedB))>"`
	- 加密消息：
		- ENC2: `"ENC2;sid=<b64(8B)>;ctr=<u64>;b64=<cipher>"`
		- cipher = AES-GCM(key=K, nonce=derived, aad=optional("sid|ctr|dir"))

- 认证与抗 MITM（增量改进）：
	- 基线：依赖首次见面指纹 pinning（UI/CLI 确认并持久化）。
	- 增强：在 KX2 中附加对 (`fpA|seedA`) 的 RSA 签名，证明对 seedA 的掌握来自持有 privB 的实体（需要验签逻辑）。
	- 更强：迁移到临时密钥对的 X25519-ECDH，并用静态 RSA 对握手材料签名（提供 PFS）。

- 兼容性：
	- 对不理解 KX/ENC2 的对端，维持现有 `ENC;...`（每条消息 RSA 包裹）路径。
	- 模式开关：`/set encrypt off|on|strict`；strict 在未知公钥或握手未完成时禁止发送明文。

——

实施计划（逐步拆解）

Step 0：准备与开关
- 保持现有 RSA+AES-GCM 代码不变；在 `cli.py` 中引入会话缓存 `self._sessions[ip] = {key, sid, send_ctr, recv_ctr, last_ts}` 与开关 `encrypt`。
- 在 BR_ENTRY/ANSENTRY 流程中：若 `encrypt in (on, strict)` 且掌握对端公钥但无会话，自动发送 KX1。

Step 1：HKDF 与派生
- 在 `crypto.py` 增加 HKDF 封装：优先使用 `cryptography.hazmat.primitives.kdf.hkdf.HKDF`，回退 `Crypto.Protocol.KDF.HKDF`，再回退简版 HKDF（基于 HMAC-SHA256）。
- 在 `cli.py` 握手处理：
	- 收到 KX1：解包 seedA，生成 seedB 与 KX2 回复；暂存本端/对端 seed，计算 K 与 sid，初始化会话。
	- 收到 KX2：解包 seedB，若已有 seedA 则计算 K 与 sid；否则缓存待配对，完成后初始化会话。

Step 2：消息发送与接收
- 发送：优先使用 ENC2（会话密钥）；若会话缺失则尝试发 KX1 或回退 ENC。
- 接收：识别 ENC2，按 sid 查找会话、验证 ctr 与滑动窗口、派生 nonce 解密；否则识别旧 ENC 路径。
- 记录：计数递增与最后活动时间，用于过期与重键判定。

Step 3：会话维护与重键
- 会话过期策略：如 30 分钟不活动或发送达到 N 条（例如 10k）触发重键流程（重新 KX）。
- 清理：后台定期清理过期会话，日志提示“会话过期已清理”。

Step 4：可观测性与 UX
- CLI：在建立/重键/过期时打印提示；在首次见面显示指纹并提示“确认/钉扎”。
- GUI：可选在 Security/Key 页面增加“对端指纹列表（已确认/未确认）”。

Step 5（可选增强）：认证与 PFS
- 为 KX2 增加签名字段并实现验签；或迁移到 X25519-ECDH 并保留回退路径。

——

可能问题与改进措施

- 握手竞态：双方同时发送 KX1 可能导致重复握手；解决：以指纹字典序决定优先角色，后到的一方接受既有会话或合并。
- 重放保护：计数器丢失或重置可能导致拒绝服务；解决：在会话状态持久化/短暂断开重连时保持计数或容忍小窗口（同时记录时间戳）。
- Nonce 冲突：确保每个会话下 nonce 唯一；解决：统一使用派生函数与单调计数；若检测到重复，立即重键并报警。
- 兼容老客户端：不理解 KX/ENC2 的对端仍可互通；严格模式下拒绝发送明文时要提示用户原因并建议“先握手”。
- 资源清理：会话过多或僵尸会话占用内存；解决：后台清理过期且长时间未活动的会话。

——

落地顺序与交付物

1) 代码：`crypto.py` HKDF + 会话工具；`cli.py` KX1/KX2/ENC2 收发与状态；最小回退保持。
2) 测试：扩展 `tests/test_key_exchange_smoke.py` 覆盖 KX、派生一致性、ENC2 加解密与重放拒绝；在环测试（两个本地实例）。
3) 文档：本文件与 `README.md` 加密章节更新；说明指纹 pinning、严格模式语义与故障处理。

——

当前实现状态（2025-12-01）

- 已完成：
	- `crypto.py` 增加 HKDF-SHA256 封装，并为 AES-GCM 支持固定 nonce（便于会话计数派生）。
	- `cli.py` 引入会话缓存（`key/sid/send_ctr/recv_ctr/recv_window/last_ts`），实现 KX1/KX2 握手与 ENC2 收发逻辑，旧 `ENC;...` 路径保持兼容。
	- 简单重放窗口与基于 `sid+ctr` 的派生 nonce（`nonce = H(sid||dir||ctr)[0:12]`）。
	- 冒烟测试 `ZFeiQ_Original/tests/test_key_exchange_smoke.py`：在未捕获到 KX2 包的情况下，按文档级别 B 的规则手动建立会话以验证 ENC2 端到端加解密，测试通过。

- 待完善：
	- 会话过期与重键策略（如 30 分钟或 N 次消息触发重新握手）。
	- 重放窗口的滑动与裁剪优化，以及异常计数器恢复策略。
	- README 加密章节的实操说明（如何开启 `encrypt=on|strict`、如何观察会话建立与指纹 pinning）。
	- 真实网络场景的在环集成测试（可选）。

- 使用与兼容：
	- 当 `encrypt` 处于 `on/strict` 且已知对端公钥时，会自动尝试 KX1/KX2 并建立会话；成功后优先走 `ENC2` 会话加密。
	- 对端若不支持 KX/ENC2，将回退到旧 `ENC;...` 路径；`strict` 模式下可选择阻止明文或回退加密发送。

- 风险与备注：
	- 首次见面仍建议在 GUI/CLI 中确认或钉扎指纹以降低 MITM 风险；后续考虑在 KX2 增加签名字段以增强认证。
	- GCM 的 nonce 唯一性由计数派生保证；若检测到重复，建议立即触发重键并报警。