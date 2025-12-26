# NZFeiQ 安全与加密说明

本文档将项目中有关加密设计、握手流程、密钥派生、消息加解密格式，以及从旧加密方案迁移到当前方案的对比与改进建议整合于一处，便于维护者与审计者查阅。

目录
- 加密设计概览
- 握手流程（KX1/KX2/ENCREADY）
- 密钥派生与 SID/nonce 设计
- 消息加/解密格式
- 安全注意事项与实现细节
- 旧方案对比与迁移原因
- 后续改进建议与测试/CI

---

## 1) 加密设计概览

相关实现文件
- 握手与会话逻辑: `NZFeiQ/core/session.py`
- 密钥/对称算法实现: `NZFeiQ/core/crypto.py`
- 核心调用位置: `NZFeiQ/core/engine.py`（触发握手/发送行为）

依赖
- 需要安装 `cryptography`（`pip install cryptography`）用于 X25519、HKDF 与 ChaCha20-Poly1305。

采用的主要原语
- X25519 (ECDH)：临时密钥交换（ephemeral ECDH）
- HKDF-SHA256：从共享 secret 派生对称密钥
- ChaCha20-Poly1305 (AEAD)：消息加密与认证

目标：在嵌入式/局域网场景下实现前向保密（PFS）、低资源消耗与较小报文开销。

---

## 2) 握手（概览）

协议消息类型（实现参考 `Session.process_packet`）
- `KX1;...;pubA=...` — 发起方发送临时公钥 pubA（Base64）。
- `KX2;...;pubB=...` — 被动方回复自己的临时公钥 pubB（Base64）。
- `ENCREADY;sid=...` — 握手完成后确认 SID（会话 ID）。

简要流程
- 发起方：生成临时 X25519 密钥对(privA/pubA)，发送 `KX1` 并置状态为 `KX_SENT`。
- 被动方：收到 `KX1` 后生成临时密钥对(privB/pubB)、回复 `KX2`，基于 privB 与 pubA 做 ECDH 派生会话密钥并发送 `ENCREADY`。
- 发起方：收到 `KX2` 后用 privA 与 pubB 做 ECDH，派生密钥并发送 `ENCREADY`。
- 双方收到 `ENCREADY` 并验证 SID 后将握手视为完成（`ESTABLISHED`）。

---

## 3) 密钥派生（Session._derive_keys）与 SID/nonce

- 使用 HKDF-SHA256：`hkdf_sha256(ikm=shared_secret, info=b"zfeiq-x25519-chacha20", length=32)` 生成 32 字节对称密钥。
- 会话 SID：取 `sha256(key).digest()[:8]`（前 8 字节），用于作为 AAD 并参与 nonce 派生。
- Nonce 派生：`nonce = sha256(sid || b"zfeiq_nonce" || ascii(ctr))[:12]`（前 12 字节用于 ChaCha20-Poly1305）。
- 派生后销毁临时私钥以保证 PFS（`local_ephemeral_priv = None`）。

注意：SID 为 8 字节以节省带宽，但在审计中需评估碰撞概率并考虑扩展为更长（例如 16 字节）以降低风险。

---

## 4) 消息加密格式与流程

发送（encrypt_msg）
- 仅在 `ESTABLISHED` 状态使用。
- 维护 `send_ctr`（从 1 开始递增），使用 SID + ctr 派生 nonce。
- 使用 ChaCha20-Poly1305 进行 AEAD 加密，`aad = sid`。
- 文本消息格式（示例）：
  `ENC;sid=<B64SID>;ctr=<ctr>;tag=<B64TAG>;b64=<B64CT>`

接收（decrypt_msg）
- 解析 `sid`、`ctr`、`b64`、`tag`，验证 SID 匹配；检查 `ctr` 未被重放（使用 recv_window 滑动窗口）。
- 以相同派生方法计算 nonce，解密并验证 tag，解密失败则拒绝并记录警告。

重放保护
- 接收端维护 `recv_window` 集合（默认保留最多 1024 条），用于检测重复 `ctr`。

---

## 5) 实现位置与细节

- `NZFeiQ/core/crypto.py`：X25519、HKDF、ChaCha20-Poly1305 的封装函数（`generate_x25519_keypair`, `derive_x25519_shared`, `hkdf_sha256`, `chacha20_encrypt`, `chacha20_decrypt`）。
- `NZFeiQ/core/session.py`：`Session.initiate_handshake`, `_handle_kx1`, `_handle_kx2`, `_handle_encready`, `_derive_keys`, `_derive_nonce`, `encrypt_msg`, `decrypt_msg`。
- `NZFeiQ/core/engine.py`：触发握手、会话管理、路由消息的上层逻辑。

---

## 6) 旧方案对比（迁移原因概要）

历史上仓库曾使用 RSA‑3072 + AES‑256‑GCM 的组合（静态 RSA 用于包装/认证），当前迁移到 X25519 + ChaCha20‑Poly1305 的主要原因：
- 提供前向保密（PFS）。
- 在嵌入式/ARM 平台上性能更优、能耗更低。
- 报文更紧凑，握手与消息开销更小，适合局域网场景。

对比要点（简述）
- 非对称：静态 RSA（旧） vs 临时 X25519（新，提供 PFS）。
- 对称 AEAD：AES‑GCM vs ChaCha20‑Poly1305（后者在某些嵌入式平台更快）。
- 认证缺口：当前握手未把 ephemeral pub 用长期身份签名，因此首次交互存在 MITM 风险（需改进）。

---

## 7) 已知安全权衡与建议改进

优先级高的改进：
1. 握手认证（必做）
   - 用长期身份密钥（例如 Ed25519）对 ephemeral pub 做签名，在 `KX1/KX2` 中携带签名并验证，以抵抗 MITM。
   - 可复用 `bridge.core.identity_pub_bytes` / `identity_priv` 实现签名。

2. 测试覆盖与 CI（必做）
   - 增加握手/解密/重放/错误 SID 等单元与集成测试，并在 CI 中运行。

中等优先级：
- 扩展 SID 长度（例如 16 字节）并改进 nonce 派生以包含更多上下文。
- 优化 `recv_window` 的滑动策略与大小，避免高丢包场景下误判或内存增长。
- 在握手中加入能力协商与回退策略（例如与仍使用 RSA 的旧客户端互通）。

低优先级：
- 更严格的会话生命周期管理与长期密钥旋转策略。

---

## 8) 测试/审计建议

- 在 CI 中把 `cryptography` 列为必装依赖并运行加密冒烟测试。
- 增加对以下场景的自动化测试：
  - KX1→KX2→ENCREADY 正常握手。
  - 错误 SID/错误 tag（应拒绝并记录）。
  - 重放攻击模拟（重复 ctr）。
  - 长时间空闲后重连与 ctr/nonce 行为。

---

## 9) 参考与历史位置

- 代码位置：
  - `NZFeiQ/core/crypto.py`
  - `NZFeiQ/core/session.py`
  - `NZFeiQ/core/engine.py`
- 旧实现参考（legacy）：`legacy_ZFeiQ/**/zfeiq_cli/crypto.py`

---

> 注：本文件由 `docs/CRYPTO.MD` 与 `docs/ENCRYPTION_MIGRATION.md` 内容合并而成，保留实现细节与迁移分析要点。如需把某部分拆分为单独审计文档（例如握手认证设计补丁或 CI 测试样例），我可以继续生成对应补丁与测试脚本。
