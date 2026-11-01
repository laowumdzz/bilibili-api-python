# Research: 基于 aiosqlite 的凭据存储管理器实现

**Feature**: `011-aiosqlite-credential-store` | **Date**: 2026-11-01

本文件消解 spec 遗留的 plan 期裁决项（加密方案细节、默认位置机制、存储结构），并记录实现前实测验证的关键事实。

## D1: Credential pydantic 化前置修复（阻塞项）

**Decision**: 在本特性范围内完成 `bilibili_api/utils/_credential.py` 中 `Credential` 的最小 pydantic 完成化：声明 7 个字段（sessdata / bili_jct / buvid3 / buvid4 / dedeuserid / ac_time_value / proxy）+ `model_config = ConfigDict(extra="allow")` + 自定义 `__init__` 首行调用 `super().__init__()`。`__init__` 既有语义（URL 编码 sessdata、proxy 透传、**kwargs 经 setattr 存为 extra）全部保留，签名不变。

**Rationale**: 工作区当前 `Credential(BaseModel)` 构造即抛 `ValueError: "Credential" object has no field "sessdata"`（pydantic v2 拒绝未声明字段赋值），基类的 `model_copy(deep=True)` 与本特性所需的 `model_dump_json()` 均无从谈起——已实测复现（2026-11-01，pydantic 2.14.2）。修复模式已实测验证：声明字段 + extra="allow" + `super().__init__()` 后，`model_dump` / `model_copy(deep=True)` / `model_dump_json` 全部回环成功，kwargs extra 无损保留。保持 `__init__` 签名与语义 → 非破坏性变更。

**Alternatives considered**:
- 等待 nonebot 分支上层 WIP 自行完成 → 阻塞本特性全部验收，不可取。
- 存储层绕开 pydantic（手工读 `__dict__` 序列化）→ 当前状态连构造都不通过，绕不开；且手工序列化脆弱、偏离 pydantic 化方向。

## D2: 静态加密方案 —— RSA-2048-OAEP 混合 AES-256-GCM，按记录封装

**Decision**: 每条凭据记录独立加密：为该记录随机生成一次性 AES-256-GCM 数据密钥，凭据 JSON 明文经 AES-256-GCM（随机 12 字节 nonce）加密；数据密钥经 RSA-2048-OAEP（SHA-256）封装。落盘 BLOB = `nonce(12B) + encrypted_dek(256B) + ciphertext + GCM tag(16B)`，外加非密码学布局头。密钥文件为 RSA-2048 密钥对 PEM（含私钥），首次使用时随机生成，权限按 OS 允许尽量收紧（POSIX 0600）。

**Rationale**: 凭据 JSON（6 字段，sessdata 常为百余字符的 URL 编码串）通常超出 RSA-2048-OAEP(SHA-256) 单块明文上限（190 字节），必须混合加密；GCM 自带认证标签，密文被篡改时解密即失败 → 天然满足"损坏显式报错、不静默读出坏数据"（FR-008 / US3）。按记录封装数据密钥实现记录级隔离，50 账号量级下每条一次 RSA 运算（毫秒级）不构成性能问题（SC-004 预算宽裕）。RSA 与 AES 均复用既有依赖 pycryptodomex（登录链路已在用），不新增加密栈。

**Alternatives considered**:
- 纯 RSA 直接加密 JSON → 超上限（190B < 典型凭据 JSON 尺寸），不可行。
- 整库单一 AES 数据密钥（首记录时生成、RSA 封装一次）→ 实现更简，但所有记录共享一把数据密钥，记录级隔离弱于按记录封装；当前规模收益不明显，不选。
- Fernet / cryptography 库 → 引入新依赖 cryptography，违反"复用既有栈"倾向。

## D3: schema 版本机制

**Decision**: 数据库内置 `meta` 表（key TEXT PRIMARY KEY, value TEXT），写入 `schema_version = "1"` 与 `store_format = "bilibili-api-credential-store"`。连接建立后先读 meta：缺失 `store_format` 或非本库标识 → `CredentialStoreCorruptException`；`schema_version` 高于当前实现 → `CredentialStoreVersionMismatchException`（提示程序需升级）；低于当前实现（未来场景）→ 同样显式报错（v1 阶段无旧版，保留对称语义）。密钥文件损坏（PEM 解析失败）→ `CredentialStoreCorruptException`。

**Rationale**: 直接落实 spec FR-012（clarify Q4：明确失败优于静默兼容）；meta 表方案是 SQLite 惯用法，读一次 O(1)。

**Alternatives considered**: 无版本管理尽力兼容 → spec Q4 已否决；完整迁移框架 → 本期范围过大，spec Q4 已否决。

## D4: 默认存储位置

**Decision**: 新增依赖 `platformdirs>=4.0`（经 `uv add`），默认目录取 `platformdirs.user_data_dir("bilibili-api", appauthor=False)`：Windows 为 `%APPDATA%\bilibili-api`，macOS 为 `~/Library/Application Support/bilibili-api`，Linux 为 `~/.local/share/bilibili-api`。默认文件名 `credentials.db` 与 `credentials.key`；目录不存在时惰性创建（含首次写库 / 写钥时）。

**Rationale**: 落实 clarify Q3 用户选择（OS 标准应用数据目录）；`appauthor=False` 避免 Windows 下多余的作者层级目录；NoneBot 场景由适配层经 localstore 解析路径后显式传入覆盖（spec Assumptions）。

**Alternatives considered**: 主目录固定路径 `~/.bilibili-api/` → 备选项，用户未选；项目根目录（cwd 依赖）→ 已否决。

## D5: 自定义异常

**Decision**: 按仓库"一文件一类"惯例新增三个异常，均继承 `ApiException`：
- `CredentialStoreException(ApiException)`——存储模块通用基类；
- `CredentialStoreCorruptException(CredentialStoreException)`——数据库文件损坏 / 非本库格式 / 解密认证失败 / 密钥文件丢失或损坏（语义统一为"存量数据不可读，需重新添加账号"）；
- `CredentialStoreVersionMismatchException(CredentialStoreException)`——schema 版本不匹配。

错误消息只含文件路径与原因类别，MUST NOT 含凭据字段值（宪法红线）。`exceptions/__init__.py` 同步导出。

**Rationale**: spec FR-008 要求项目自定义异常；两类语义边界清晰（损坏 vs 版本），调用方可分别处理"重新添加"与"升级程序"。

**Alternatives considered**: 单一异常 + reason 字段 → 调用方需解析消息字符串区分场景，不如类型层级直接。

## D6: 表结构与插入顺序

**Decision**: 两张表：

```sql
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credential (
    uid       INTEGER PRIMARY KEY,
    order_seq INTEGER NOT NULL UNIQUE,
    data_enc  BLOB    NOT NULL
);
```

`order_seq` 取当前 `MAX(order_seq)+1`（空表从 1 起）：新增分配、覆盖保留原值、删除留空洞——保证 `get_credential(uid=None)` 与 `read_data()` 按 `ORDER BY order_seq` 还原插入顺序（uid 数值序 ≠ 插入序，故不能用 rowid 序代替）。持久化粒度：`store_data(snapshot)` 在单个事务内 `DELETE FROM credential` + 全量 INSERT + 更新 meta → 天然满足 FR-004 原子性（快照语义，与基类 `_persist` 一致）。

**Rationale**: 基类 `store_data` 契约即"全量快照持久化"，事务内全量重写最简单且原子性免费获得；50 记录量级重写成本可忽略。

**Alternatives considered**: 按记录 UPSERT 增量写 → 需要基类改造出逐条持久化钩子，超出"实现抽象方法"的边界，且原子窗口更碎；用自增 rowid 表达插入序 → uid 是 INTEGER PRIMARY KEY 时 rowid 即 uid，顺序错。

## D7: 连接与事件循环管理

**Decision**: aiosqlite 连接在实例首次数据库操作时惰性创建（`aiosqlite.connect(path)`），创建时记录 `asyncio.get_running_loop()`；后续操作校验当前 loop 一致，不一致抛 `ArgsException`（把基类"同一 loop"约定从文档升级为防御性检查）。提供实现类专属 `async def close()` 用于显式关闭（基类无此 API，属实现附加，向后兼容）。测试场景间以 close() + 清除子类单例获得"重启"模拟；SC-001 的跨进程证明用独立子进程脚本完成。

**Rationale**: aiosqlite 连接绑定创建它的 loop，跨 loop 使用会产生难以理解的挂起 / 报错；提前显式失败符合"宁可不工作不能悄悄坏"。close() 解决测试中连接线程堆积问题。

**Alternatives considered**: 每 操作开关连接 → 性能浪费且丢失"绑定 loop"语义；不做 loop 校验 → cryptic failure，违背 FR-008 精神。

## D8: 单例与构造参数

**Decision**: 遵守基类"每个具体子类单例"。构造签名 `__init__(self, db_path=None, key_path=None)`：仅在**首次实例化**生效（此后 `_ready` 跳过初始化）；后续 `Impl(...)` 传入与已配置不同的路径 → 抛 `ArgsException`（防止调用方误以为新参数生效）。路径参数接受 `str | Path`；`None` 时用 D4 默认值。`read_data()` 为 classmethod（基类抽象签名），实现内经 `cls()` 取单例后复用实例连接与配置。

**Rationale**: 单例与参数化天然紧张，"首实例化生效 + 后续冲突显式报错"是保持基类契约（`load()` 内 `cls()` 无参调用）不被破坏的最小方案。

**Alternatives considered**: 工厂函数绕开单例 → 基类 `__new__` 已强制单例，绕不开；全局可变配置 → 隐式状态更难排查。

## D9: 测试策略（离线全覆盖）

**Decision**: `tests/test_offline_credential_store_sqlite.py`，全部离线，凭据值用假数据（如 `"fake_sessdata"`）：
- **回环**：add → get 一致性；覆盖返回 False / remove 返回 True；auto_persist=False 不落盘。
- **重启恢复**：同文件、清理单例后重建实例 → 全量恢复；`get_credential(None)` 返回最早插入者（插入乱序 uid 验证 order_seq）。
- **跨进程证明**（SC-001）：子进程 `sys.executable -c` 脚本分两次运行（写 / 读），临时目录传参。
- **加密静态检查**（SC-002）：以二进制读库文件，断言 6 个假字段值均不出现（0 命中）。
- **密钥丢失 / 损坏**（SC-003）：删 key 文件 / 写坏 PEM → `CredentialStoreCorruptException`，且库文件未被清空。
- **库损坏**（US3）：截断 / 随机字节覆写 db → 显式异常，不被静默重建。
- **版本不匹配**（FR-012）：手工把 meta.schema_version 改成 "999" → `CredentialStoreVersionMismatchException`。
- **性能**（SC-004）：50 账号 load 计时断言 < 3s（宽裕上限，防回归而非基准测试）。
- **凭据脱敏**：触发异常时断言消息不含假字段值。
- 单例隔离技巧：每个测试定义局部子类（各自独立 `_instance`），或 fixture 中 `cls.__dict__.pop("_instance", None)`；临时文件统一 `tmp_path`。

**Rationale**: 宪章 IV 离线层要求 + spec FR-011；子进程为本地 `sys.executable` 调用，属本机操作，不触外网。

**Alternatives considered**: 仅同进程双实例模拟重启 → 无法证明 SC-001"完全重启进程"语义，补子进程用例补强。

## 实测验证记录

| 验证项 | 结果 |
|--------|------|
| 当前工作区 `Credential(sessdata=...)` 构造 | ❌ `ValueError: "Credential" object has no field "sessdata"`（pydantic 2.14.2） |
| 声明字段 + `extra="allow"` + `super().__init__()` 模式 | ✅ `model_dump` / `model_copy(deep=True)` / `model_dump_json` / kwargs extra 全部回环成功 |
| aiosqlite>=0.22.1 已在 pyproject 依赖 | ✅（此前无任何模块使用） |
| pycryptodomex 既有（登录 RSA 在用，含 AES） | ✅ |
