## 架构重构计划 — 前后端彻底分离（Core / Frontend）

> 目标：构建“洁净架构”，彻底解耦业务逻辑（Core）与用户界面（CLI/GUI）。此举旨在支持未来的**嵌入式无头模式（Headless）**运行，并为将来平滑移植到 **C/C++ 高性能版本** 建立标准蓝图。

### 一、总体设计原则

1. **Core 纯净性**：`zfeiq_core` 内部严禁包含任何 UI 代码（print/input/Qt），仅通过 API 和事件与外界交互。
2. **强类型约束**：引入 Pydantic 或严格的 Type Hints 定义数据模型（DTO），模拟 C++ 结构体，确保数据流清晰、类型安全。
3. **事件驱动**：使用发布/订阅（Pub/Sub）模式替代紧耦合的回调，实现逻辑层与 UI 层的完全解耦。
4. **持久化分离**：引入轻量级 ORM（如 Peewee/SQLite），替代单纯的 JSON 文件存储，提升历史记录查询性能。

### 二、目录结构（规划草案）

- `zfeiq_core/`（后端核心，未来可被 C++ 库替换）
  - `__init__.py`
  - `api.py`：对外暴露的门面接口（Facade），如 `ZFeiQCore` 类（Login/Send/GetHistory）。
  - `events.py`：定义系统事件主题（Topic Strings），如 `msg.recv`、`file.progress`。
  - `entities/`：**[新增]** Pydantic 数据模型，对应 C++ 结构体。
    - `user.py` (`User`), `message.py` (`Message`), `file_offer.py` (`FileOffer`)。
  - `services/`：**[新增]** 具体业务逻辑实现。
    - `network.py`: UDP 广播与 TCP 传输。
    - `crypto.py`: RSA/AES 加解密。
    - `history.py`: SQLite 数据库操作封装。
  - `persistence.py`: 配置状态管理（JSON）。

- `zfeiq_gui/`（GUI 前端）
  - `backend.py` 改造：
    - 变为 `CoreBridge`（适配器模式）。
    - 负责订阅 Core 的 Pub/Sub 事件，并将其转发为 Qt Signals（跨线程安全）。
    - 负责将 UI 操作转译为 Core API 调用。

- `zfeiq_cli/`（CLI 前端）
  - 负责参数解析与控制台渲染，直接调用 Core API 并打印事件回调。

### 三、分阶段实施步骤

1. **定义 Core API 契约（Interface Definition）**
    - 编写抽象基类，明确输入输出类型。
    - 此时不改变现有逻辑，仅梳理接口签名，确保所有网络/文件操作都有对应的 API 方法。

2. **数据模型标准化 (Preparing for Structs)**
    - 引入 Pydantic，将目前散落在字典里的 `packet` 数据封装为强类型对象。
    - 这一步将大大降低未来移植 C++ 时的理解成本。

3. **引入事件总线 (Event Bus)**
    - 使用 `PyPubSub` 替换现有的 `_on_recv` 回调链。
    - 建立清晰的事件层级，例如 `net.state.online`, `chat.message.incoming`。

4. **持久化层升级**
    - 将聊天记录写入迁移至 SQLite (via Peewee)。
    - 优化启动速度，不再一次性加载所有历史记录。

5. **C++ 移植准备（远期规划）**
    - 当 Python 版 Core 稳定后，可依据 `zfeiq_core` 的结构，使用 C++ (Qt/Boost) 逐步重写底层，对外保持相同的 Python 绑定接口，实现性能的无缝升级。
