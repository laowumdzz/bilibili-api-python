# Feature Specification: 基于 aiosqlite 的凭据存储管理器实现

**Feature Branch**: `011-aiosqlite-credential-store`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "使用aiosqlite写一个BaseCredentialStoreManager实现类"

## Clarifications

### Session 2026-11-01

- Q: 落盘凭据的 RSA-2048 静态加密保留在本特性内还是拆分为独立后续特性？ → A: 保留在本特性内（P2 用户故事），不拆分。
- Q: 首次使用是否从既有单账号凭据缓存（TEMP 缓存 / .bilibili.cookie）导入存量凭据？ → A: 不导入，新库从零开始，账号由上层显式添加。
- Q: 独立使用时存储文件与密钥文件的默认位置解析到哪个目录？ → A: 操作系统标准应用数据目录（经 platformdirs 解析，如 Windows %APPDATA%），支持自定义路径覆盖。
- Q: 新旧版本程序交叉打开存储文件（存储结构变更后）如何处理？ → A: 存储文件内记录 schema 版本号，打开时版本不匹配（过旧或过新）即显式报错，不做静默兼容。
- Q: 运行日志应达到什么详细程度？ → A: 标准 logging 记录关键事件（加载条数、增删改结果），任何情况下不输出凭据字段值。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 持久化存储管理器落地 (Priority: P1)

下游开发者（多账号机器人 / NoneBot 适配层的维护者）获得一个真正可用的凭据存储管理器：凭据按 UID 写入本地嵌入式数据库文件，进程重启后通过 load() 完整恢复；基类既有操作（添加 / 获取 / 移除 / 列举 / 计数）语义完全不变，且每次变更自动落盘。

**Why this priority**: 这是本特性的核心交付——抽象基类目前没有任何实现，凭据只能存在于内存中、进程结束即丢失；没有它，"多账号支持、按添加顺序选账号"的设计（决策树）完全无法工作。

**Independent Test**: 在离线环境下实例化实现类、添加两个凭据、重新 load 并断言全部恢复；全程无外网请求、无真实凭据。

**Acceptance Scenarios**:

1. **Given** 全新环境（无存储文件），**When** 创建实现类实例并依次添加两个不同 uid 的凭据，**Then** 两条凭据均可取出且与写入内容一致，存储文件在数据目录生成。
2. **Given** 已有包含两条凭据的存储文件，**When** 在新的进程中 load()，**Then** 凭据数量与 uid 集合完全恢复，且 get_credential(uid=None) 返回最早添加的那条（插入顺序跨进程保持）。
3. **Given** 已有存储文件，**When** 覆盖同 uid 的凭据（add 返回 False）并移除另一 uid（remove 返回 True），**Then** 重新 load 后覆盖生效、被移除的 uid 不再存在。
4. **Given** 以 auto_persist=False 添加凭据，**When** 仅执行该操作，**Then** 内存态立即生效而存储文件保持不变；后续任一 auto_persist=True 操作把当前内存态完整落库。

---

### User Story 2 - 落盘凭据静态加密 (Priority: P2)

依据决策树（本地存储加密）：落盘文件中永远找不到任何凭据字段明文；加密使用 RSA-2048 密钥对，随机生成、仅存本地，密钥被删除则已有存储不可读、需重新添加账号。加解密对上层调用方完全透明。

**Why this priority**: 凭据即账号身份（SESSDATA 等同登录态），静态明文落盘会把"本地文件被拷贝"变成"账号被盗"，是用户在设计决策中明确的红线级要求；但相对 P1 的"能用"，本篇属于"用得安全"，且可独立开发与验收。

**Independent Test**: 添加凭据后以二进制方式检索存储文件，确认 6 个凭据字段值均不以明文出现；删除密钥文件后 load() 显式失败并提示重新添加。

**Acceptance Scenarios**:

1. **Given** 全新环境，**When** 首次添加凭据，**Then** 随机密钥对生成并仅写入本地数据目录（不随代码 / 仓库分发），存储文件中检索不到任何凭据字段明文。
2. **Given** 已有加密存储，**When** 正常 load 并取出凭据，**Then** 解密后的字段值与写入时完全一致（对上层透明）。
3. **Given** 密钥文件被删除或损坏，**When** 执行 load() 或读操作，**Then** 显式抛出异常并提示需重新添加账号；存储文件不被删除、不降级为明文、不静默重建密钥。

---

### User Story 3 - 异常防御与数据安全 (Priority: P3)

存储文件损坏、路径不可写、uid 不一致等异常场景下，实现类显式报错（项目自定义异常），绝不静默清空数据、不产生半写状态、不在任何错误信息中泄露凭据字段值。

**Why this priority**: 凭据存储是"丢了要重新扫码登录、悄悄坏了可能丢账号"的低频高损组件，宁可不工作也不能悄悄坏；但触发前提均为异常场景，故排在功能与安全之后。

**Independent Test**: 人为构造损坏的存储文件与不可写路径，断言报错类型、错误信息不含凭据内容、既有数据未被清空。

**Acceptance Scenarios**:

1. **Given** 存储文件被截断或损坏，**When** load()，**Then** 抛出项目自定义异常（信息不含凭据内容），且既有文件不被静默清空或重建。
2. **Given** 存储路径不可写（磁盘满或权限不足），**When** add_credential(auto_persist=True)，**Then** 抛异常、内存态不受影响、无半写残留。
3. **Given** uid 与 credential.dedeuserid 不一致，**When** add_credential，**Then** 基类 ValueError 原样传播，且不落库。

---

### Edge Cases

- 存储文件不存在（首次使用）→ 视为空库，正常建库并返回空数据，不报错。
- 密钥文件存在但与数据不匹配（如换了密钥再读旧库）→ 解密失败按"密钥损坏"处理：显式报错，不静默清数据。
- 同进程重复实例化 → 沿用基类"每个具体子类单例"约定，返回同一实例，不产生第二个连接。
- 跨事件循环使用实例 → 沿用基类"实例与事件循环绑定"约定，本特性不提供跨 loop 迁移；实现不得在该约束之外引入新的隐藏阻塞。
- 凭据字段值包含特殊字符（如 URL 编码的 SESSDATA）→ 序列化与加解密须无损还原。
- 存储文件由更新或更旧的程序版本打开（schema 版本不匹配）→ 显式报错并说明版本不兼容，不做静默读写（FR-012）。
- 大量账号（如 50 个）→ 全量读取与单条增删须在常规本地磁盘耗时内完成（见 SC-004）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 库内 MUST 提供 `BaseCredentialStoreManager` 的具体实现类，基于 aiosqlite 异步访问单文件嵌入式 SQLite 数据库，与基类同层放置（`bilibili_api/utils/`），不依赖 NoneBot 运行时即可独立使用。
- **FR-002**: 实现 MUST 落实基类两个抽象方法 `read_data()`（全量读出）与 `store_data()`（全量持久化快照），并保持基类既有公共行为（add / get / remove / get_all_uids / len、auto_persist 默认持久化、uid 与 dedeuserid 一致性校验）语义完全不变。
- **FR-003**: 存储以 UID 为主键：同 uid 覆盖、remove 真删除；凭据记录的插入顺序 MUST 跨进程持久保持（支撑"按添加顺序选账号"）。
- **FR-004**: 每次持久化 MUST 原子生效：任一次写入失败（磁盘 / 权限 / 序列化错误）MUST 抛异常，且不破坏上一次已落库的完整数据，内存态亦不受损——实现为 persist 失败时回滚该次内存变更后重抛原异常；此失败路径回滚是对基类行为的显式加强，不视为破坏 FR-002 的"语义不变"约束（该约束辖定成功路径行为与契约签名）。
- **FR-005**: 凭据静态加密 MUST 以 RSA-2048 落实：密钥对随机生成、仅存本地数据目录、永不入库或随代码分发；落盘内容 MUST NOT 出现任何凭据字段（sessdata / bili_jct / dedeuserid / buvid3 / buvid4 / ac_time_value）明文。
- **FR-006**: 密钥文件缺失或损坏时 MUST 显式报错并提示重新添加账号；MUST NOT 静默重建密钥，MUST NOT 静默清空已有存储。
- **FR-007**: 默认存储位置 MUST 为操作系统标准应用数据目录（经 platformdirs 解析，如 Windows %APPDATA%），并支持调用方自定义路径覆盖；存储文件与密钥文件 MUST 加入 .gitignore，绝不入库。
- **FR-008**: 数据库文件损坏 / 无法打开时 MUST 显式抛项目自定义异常（信息中不得含凭据字段值），MUST NOT 静默清空重建。
- **FR-009**: 遵循异步优先（宪法 I）：所有公共方法均为 async；异步路径 MUST NOT 引入同步阻塞 IO；数据库连接 MUST 在首次使用时创建并与事件循环绑定，与基类"同一 loop 内使用"约定一致。
- **FR-010**: 代码 MUST 兼容 Python 3.10；公共函数提供完整类型注解与中文 docstring（Args / Returns / Raises）；合入前通过 `uv run python scripts/lint.py` 全量门禁并重新生成文档。
- **FR-011**: 测试 MUST 以离线用例覆盖（tests/test_offline_*.py：增删改查、重启恢复、插入顺序、加密静态检查、损坏与不可写场景），禁止外网请求与真实凭据。
- **FR-012**: 存储文件内 MUST 记录 schema 版本号；打开时版本不匹配（程序过旧或过新）MUST 显式报错（信息不得含凭据字段值），MUST NOT 静默按兼容模式读写。
- **FR-013**: 运行诊断 MUST 使用标准 logging（模块级 logger），记录关键事件（加载条数、添加 / 覆盖 / 移除结果等）；任何日志 MUST NOT 输出凭据字段值（宪法红线），禁止 print()。

### Key Entities *(include if feature involves data)*

- **凭据记录**：UID（主键）↔ Credential 实例（6 个凭据字段）↔ 插入顺序；同一 UID 仅一条记录。
- **存储文件**：本地单文件嵌入式数据库，落盘全部凭据记录，静态加密。
- **密钥文件**：RSA-2048 密钥对，首次使用时随机生成、仅存本地数据目录；丢失即判"存量数据不可恢复"，需重新添加账号。
- **管理器实例**：每个具体子类单例，绑定创建时的事件循环（基类既有约定，不在本特性内改变）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 添加 ≥3 个账号后完全重启进程并 load()，账号数量、UID 集合与"首条账号 = 最早添加者"全部一致，全程无人工干预。
- **SC-002**: 对落盘文件做全文件检索，6 个凭据字段值均不以明文出现（0 处命中）。
- **SC-003**: 删除密钥文件后执行读取，100% 显式失败并提示重新添加，而非返回空数据、明文或静默重建。
- **SC-004**: 单条凭据的添加 / 覆盖 / 移除（含落盘）在本机常规磁盘上 1 秒内完成；50 账号全量 load 在 3 秒内完成。
- **SC-005**: 离线测试套件全绿、既有测试零回归；合入门禁（`uv run python scripts/lint.py`）全绿。

## Assumptions

- 实现类是独立库组件（不绑定 NoneBot）；NoneBot 适配层后续按需消费。决策树中"账号过期尝试刷新、失败切换下一账号"与"连接直播间时机（ON/AUTO/MANUAL）"属于上层调度逻辑，不在本特性范围。
- 前置依赖：完成工作区 `Credential`（bilibili_api/utils/_credential.py）的 pydantic 化最小修复（声明字段 + `extra="allow"` + `__init__` 首行 `super().__init__()`，构造签名与语义不变，详见 plan research D1）；当前未修复时构造即抛 ValueError，是本特性全部序列化与持久化的阻塞前提。
- 不从既有单账号凭据缓存（TEMP 登录缓存 / .bilibili.cookie）导入存量凭据；新库从零开始，账号一律由调用方显式添加。
- 数据库与密钥默认放操作系统标准应用数据目录（经 platformdirs 解析，为新增依赖、经 uv 管理）；NoneBot 场景下适配层可经 nonebot-plugin-localstore 解析路径后显式传入覆盖。
- 加密的实现细节（直接 RSA 加密小块数据或混合加密、密钥文件格式）留给 plan 阶段裁决；本 spec 只约束"静态不明文 + RSA-2048 随机密钥对仅存本地 + 密钥丢失需重新添加账号"。
- 以单进程使用为主；跨进程并发写同一存储文件不在本特性目标内（嵌入式数据库引擎自身的事务保护作为兜底）。
- Windows（开发环境）与 POSIX（CI 3.10 / 3.13）下路径与文件行为一致。
