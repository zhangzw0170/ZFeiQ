# 握手认证（Handshake Authentication）设计补丁说明

目标
- 在现有 X25519 握手（KX1/KX2/ENCREADY）基础上加入对 ephemeral 公钥的签名验证，防止首次交互的中间人攻击（MITM）。

设计要点
1. 使用长期身份密钥对 ephemeral 公钥签名
   - 假设已有长期身份密钥对（`identity_priv` / `identity_pub_bytes`），采用 Ed25519 或使用现有长期私钥做签名（若长期密钥为 X25519，可考虑同时维护 Ed25519 用于签名）。
   - 在 KX1/KX2 报文中追加签名字段：`sig=<b64(sig)>`，签名内容为 `b64(ephemeral_pub)||context`。
   - `context` 建议包含：协议版本、发起方长期公钥指纹（便于快速验证）、时间戳（可选，限制签名有效期）。

2. 报文格式（示例）
- 发起方发送（KX1）:
  `KX1;ver=2;fp=<b64(fp)>;pubA=<b64(pubA)>;sig=<b64(sigA)>`
  - 其中 `sigA = Sign(identity_priv, b64(pubA) || b"|" || ver || b"|" || fp)`

- 应答方发送（KX2）:
  `KX2;ver=2;fp=<b64(fp)>;pubB=<b64(pubB)>;sig=<b64(sigB)>`

3. 验证流程
- 接收方收到 KX1/KX2 后：
  - 解析出 `pubX` 与 `sig`。
  - 通过 `fp` 或已知长期公钥查找对端长期公钥；若不存在长期公钥，可按策略：
    - 若有信任引导通道（out-of-band）则验证并记住对端长期公钥；
    - 否则降级为「警告并允许」或直接拒绝（视安全策略决定）。
  - 使用对端长期公钥验证签名 `sig`。若验证失败则拒绝握手并记录警告/日志。

4. 兼容性/回退策略
- 为兼容不支持签名的旧客户端：
  - 在报文中保留 `ver` 字段并在建立连接时做能力协商。
  - 若对端不返回 `sig` 字段或 `ver` 表示不支持签名，则可在 UI/日志中给出安全警告并允许用户选择是否继续（不默许）。

5. API & 实现位置建议
- 在 `core/engine.py` 或 `core/session.py` 的握手触发/处理函数中增加签名/验证调用。
- 在 `core/crypto.py` 增加 `sign_bytes(private, data)` 与 `verify_bytes(public, data, sig)` 封装（使用 `cryptography.hazmat.primitives.asymmetric.ed25519`）。

6. 测试建议
- 单元测试：对 `sign_bytes/verify_bytes` 做正/负样例测试。模拟 KX1 不含 `sig`、含伪造 `sig`、正确 `sig` 三种场景。
- 集成测试：在 `test/` 中增加双节点握手测试，分别模拟支持签名与不支持签名的节点，断言期待行为（接受/拒绝/记录警告）。

7. 部署注意
- 变更将要求用户或设备至少在首次安全引导时交换长期公钥指纹，或启用 Trust-On-First-Use（TOFU）并在 UI 中提示风险。

参考
- `docs/SECURITY.md`（总体安全设计）
- `NZFeiQ/core/session.py`、`NZFeiQ/core/crypto.py`（实现位置）

---

下一步：如你确认此设计，我可以实现对应的代码补丁（`core/crypto.py` 新增签名 API；`session.py`/`engine.py` 在发送/接收 KX1/KX2 时附带/验证签名），并附带 pytest 测试用例。