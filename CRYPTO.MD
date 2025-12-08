# NZFeiQ 加密设计说明

本文档概述项目中使用的加密原语、握手流程、密钥派生与消息加/解密格式。旨在为维护者与审计者提供一个简明参照。

相关实现文件
- 握手与会话逻辑: `NZFeiQ/core/session.py`
- 密钥/对称算法实现: `NZFeiQ/core/crypto.py`
- 核心调用位置: `NZFeiQ/core/engine.py`（触发握手/发送行为）

依赖
- 需要安装 `cryptography`（`pip install cryptography`）用于 X25519、HKDF 与 ChaCha20-Poly1305。

1) 使用的原语
- X25519 (ECDH): 用于临时密钥交换 (ephemeral ECDH)，库：`cryptography.hazmat.primitives.asymmetric.x25519`。
- HKDF-SHA256: 将 ECDH 共享密钥扩展/派生为对称密钥，info 字段为 `b"zfeiq-x25519-chacha20"`。
- ChaCha20-Poly1305 (AEAD): 用于消息加密和认证（16B tag），12B nonce，32B 对称密钥，aad 使用会话 SID。

2) 握手（概览）

- 协议消息类型（见 `Session.process_packet` 的分支）：
  - `KX1;...;pubA=...` — 发起方发送自己的临时公钥 pubA（Base64）。
  - `KX2;...;pubB=...` — 被动方回复自己的临时公钥 pubB（Base64）。
  - `ENCREADY;sid=...` — 握手完成后，用于确认 SID（会话 ID）。

- 发起方（调用 `initiate_handshake()`）：
  1. 生成一个临时 X25519 密钥对 (privA, pubA)，保存私钥到 `local_ephemeral_priv`。
  2. 发送文本消息 `KX1;ver=2;fp=;pubA=<b64(pubA)>`。
  3. 将自身状态置为 `KX_SENT`。

- 被动方收到 `KX1`（`_handle_kx1`）：
  1. 解析出对端 pubA。
  2. 生成自己的临时 X25519 密钥对 (privB, pubB)。
  3. 发送 `KX2;ver=2;fp=;pubB=<b64(pubB)>`。
  4. 使用 privB 与 pubA 做 ECDH，得到共享 secret，调用 `_derive_keys(shared_secret)` 派生会话密钥与 SID。
  5. 发送 `ENCREADY;sid=<b64(sid)>`。

- 发起方收到 `KX2`（`_handle_kx2`）：
  1. 解析 pubB。
  2. 使用此前保存的 `local_ephemeral_priv` (privA) 与 pubB 做 ECDH，得到共享 secret，调用 `_derive_keys(shared_secret)` 派生会话密钥与 SID。
  3. 发送 `ENCREADY;sid=<b64(sid)>`。

- 收到 `ENCREADY` 的处理（`_handle_encready`）：
  - 若本端已经处于 `ESTABLISHED` 且 SID 匹配，则将 `peer_ready = True`。这只是一个确认通道开启的机制。

3) 密钥派生（Session._derive_keys）
- 使用 `hkdf_sha256(ikm=shared_secret, info=b"zfeiq-x25519-chacha20", length=32)` 生成 32 字节对称密钥（ChaCha20 key）。
- 会话 SID (`sid`) 取自 `sha256(key).digest()[:8]`（前 8 字节）。SID 用于作为 AAD，并参与 nonce 派生与消息绑定。
- 派生后：`state` 置为 `ESTABLISHED`，并且会销毁临时私钥 (`local_ephemeral_priv = None`) 以实现前向保密（PFS）。

4) 消息加密格式与流程
- 发送 (Session.encrypt_msg)：
  1. 仅在 `ESTABLISHED` 状态可用。维护 `send_ctr`（从 1 开始递增）。
  2. Nonce 由 `_derive_nonce(sid, ctr)` 生成：
     - 计算 sha256(sid || b"zfeiq_nonce" || ascii(ctr))，取前 12 字节作为 ChaCha20 nonce。
  3. 使用 `ChaCha20-Poly1305` 对明文进行 AEAD 加密，`aad=self.sid`。
  4. 返回字符串格式（文本消息）:
     `ENC;sid=<b64(sid)>;ctr=<ctr>;tag=<b64(tag)>;b64=<b64(ciphertext)>`

- 接收 (Session.decrypt_msg)：
  1. 解析字段并校验 `sid` 与本地 SID 是否匹配（否则拒绝）。
  2. 检查 `ctr` 未被见过（重放保护）：若已在 `recv_window` 中，则视为重放攻击并拒绝。
  3. 使用相同的 nonce 派生函数与 `sid`（作为 AAD）解密 `ciphertext+tag`，若验证失败则抛出异常。
  4. 将 `ctr` 加入 `recv_window`；`recv_window` 保持一个滑动集合（最多保持 1024 个条目，超过会删除最小的序号）。

5) 非常重要的细节与安全考虑
- Nonce 设计：nonce = sha256(sid || "zfeiq_nonce" || ctr)[:12]，因此 nonce 与 SID + 计数器共同确定，避免重复 nonce 的概率；但仍要保证 `ctr` 单调递增且不可被重置以防 nonce 重用。
- AAD 使用 `sid`，把 SID 绑定进 AEAD 验证，防止跨会话重放/混淆。
- SID 仅 8 字节（64 bit），用于节省协议带宽；实际加密强度仍由 32 字节对称密钥与 AEAD 提供，SID 长度对安全的影响主要体现在 nonce/标识上——审计时请留意 SID 的碰撞概率与协议实现环境。
- PFS：临时 X25519 私钥在握手完成后被丢弃（`local_ephemeral_priv = None`），若长期保存会话密钥则不影响对已建立通道的长期安全性，但是对长期密钥泄漏风险请根据使用场景评估。
- 重放窗口：接收端保留 `recv_window` 集合（最大 1024 条目），作为简单的重放检测；在高丢包或长时间空闲场景下需评估窗口行为（可能导致内存增长或误判）。

6) 消息示例（Base64 片段用 <> 表示）
- 握手发起： `KX1;ver=2;fp=;pubA=<B64PUBA>`
- 握手应答： `KX2;ver=2;fp=;pubB=<B64PUBB>`
- 握手完成广播： `ENCREADY;sid=<B64SID>`
- 加密消息： `ENC;sid=<B64SID>;ctr=1;tag=<B64TAG>;b64=<B64CT>`

7) 与代码的对应位置
- `NZFeiQ/core/crypto.py`：
  - `generate_x25519_keypair`, `derive_x25519_shared`（ECDH）
  - `hkdf_sha256`（HKDF-SHA256）
  - `chacha20_encrypt`, `chacha20_decrypt`（ChaCha20-Poly1305 的封装）
- `NZFeiQ/core/session.py`：
  - `Session.initiate_handshake`, `_handle_kx1`, `_handle_kx2`, `_handle_encready`
  - `Session._derive_keys`, `_derive_nonce`, `encrypt_msg`, `decrypt_msg`

8) 兼容性与扩展建议
- 当前握手协议在消息中携带 `ver=2` 字段与 `fp=` 占位（fp 用于指纹/公钥变化检测），可在后续版本中扩展为更复杂的信任验证（例如使用长期身份密钥签名临时公钥）。
- 若需更强的抗重放/同步策略：考虑基于时间窗口或滑动计数器协议并在必要时加入序列号确认消息。
- 如果关注 SID 的碰撞或信息量，可将 SID 扩展为 16 字节并在解密时用更多位作为 AAD/nonce材料。

最后：此设计在实现上权衡了协议简单性、资源占用与常见的 P2P 局域网场景安全性。若你需要对抗更高级的威胁（如主动中间人、长期密钥泄露的复杂清理策略），建议增加长期身份签名对 ephemeral pub 的签署、以及更严格的会话生命周期管理。

-- 文档结束 --
