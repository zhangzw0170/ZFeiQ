# zfeiq_core — 文档

目标：把业务逻辑与网络/持久化/加密集中在 `zfeiq_core` 中，供 CLI/GUI 调用。

当前状态（实现/已验证）
- 事件总线：`EventBus`（`zfeiq_core/events.py`）。
- 门面：`ZFeiQCore`（`zfeiq_core/api.py`）— login/send_message/get_history、网络/协议/密钥挂载方法。
- 实体：`Message` / `User` / `FileOffer`（基于 `pydantic`，在 `zfeiq_core/entities/`）。
- 服务：
  - `NetworkService`（`zfeiq_core/services/network.py`）— UDP listener + sender，发布 `net.udp.recv` 事件。
  - `ProtocolService`（`zfeiq_core/services/protocol.py`）— IPMSG 报文解析，发布 `msg.incoming`, `file.offer`, `user.online` 等事件。
  - `HistoryService`（`zfeiq_core/services/history.py`）— sqlite 消息存储。
  - `CryptoService`（`zfeiq_core/services/crypto.py`）— RSA 与 AES‑GCM 实现，含保存/加载 PEM 与指纹工具。

未完成 / 下一步计划（建议优先级）
1. FileService：实现 TCP 2425 文件映射与 `GETFILEDATA` 处理（兼容 IPMSG 附件下载流程）。
2. 更细粒度事件（file.transfer.progress, file.transfer.done）。
3. 单元测试：protocol/crypto/history/network 的自动化测试。

如何进行贡献与调试
- 本地运行 demo：参见 `ZFeiQ_Python` 根目录下的 demo 脚本（`run_demo_*.py`）。
- 手工测试网络：利用 loopback（127.0.0.1）与 `run_demo_network.py` 验证 net->core 事件流。

文档维护
- 此文件应及时同步 `zfeiq_core` 内新增的 API/事件与配置项（例如：保活间隔、绑定 IP、KEY 路径等）。
