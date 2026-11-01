# Data Model: 基于 aiosqlite 的凭据存储管理器实现

**Feature**: `011-aiosqlite-credential-store` | **Date**: 2026-11-01

## 实体总览

```text
┌─────────────────────────────┐        ┌──────────────────────────────┐
│ SQLiteCredentialStoreManager │ 1..1 ─ │ SQLite 数据库文件 (credentials.db) │
│  （每具体子类单例，绑定 loop）   │        │   ├─ meta 表                  │
│                              │        │   └─ credential 表 (N 条记录)  │
│  1..1 ─ RSA-2048 密钥文件      │        └──────────────────────────────┘
│  (credentials.key, PEM)      │                 ▲
└─────────────────────────────┘        加密 BLOB (D2) 封装
```

## 实体定义

### 1. 凭据记录（credential 表行）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `uid` | INTEGER | PRIMARY KEY | 用户 ID；与凭据 `dedeuserid` 严格一致（基类校验） |
| `order_seq` | INTEGER | NOT NULL UNIQUE | 插入顺序号：新增取 `MAX+1`，覆盖保留原值，删除留空洞；读取按其升序还原"按添加顺序选账号" |
| `data_enc` | BLOB | NOT NULL | 加密载荷，布局见下"加密 BLOB" |

**加密 BLOB 布局**（D2）：

```text
偏移   长度    内容
0      4      魔数 b"BACS"（bilibili-api credential store，非安全边界，仅快速识别）
4      12     AES-GCM nonce（每记录随机）
16     256    RSA-2048-OAEP(SHA-256) 封装的一次性 AES-256 数据密钥
272    n      AES-256-GCM 密文（凭据 JSON，UTF-8）
272+n  16     GCM 认证标签
```

**凭据 JSON**（`data_enc` 密文明文形态）：`Credential` 实例的 `model_dump_json()` 输出，字段集为 6 个凭据字段（sessdata / bili_jct / dedeuserid / buvid3 / buvid4 / ac_time_value）+ proxy + 调用方经 kwargs 注入的任意 extra 字段（`extra="allow"`，D1）。读取时 `Credential(**parsed)` 重建。

### 2. 元数据（meta 表行）

| key | value | 说明 |
|-----|-------|------|
| `store_format` | `"bilibili-api-credential-store"` | 库标识；缺失 / 不符 → `CredentialStoreCorruptException` |
| `schema_version` | `"1"`（当前） | 高于实现已知版本 → `CredentialStoreVersionMismatchException`；低于 → 同样显式报错（v1 阶段保留对称语义） |

### 3. 密钥文件（credentials.key）

| 属性 | 值 |
|------|-----|
| 格式 | PEM，含 RSA-2048 私钥（公钥可从私钥推导，不单独落盘） |
| 生成 | 首次需要时随机生成一次，此后只读复用 |
| 丢失 / 损坏语义 | 存量数据判不可恢复 → `CredentialStoreCorruptException`（提示重新添加账号）；MUST NOT 静默重建（FR-006） |
| 位置 | 与数据库同目录；默认经 platformdirs（D4），可显式覆盖 |

### 4. 管理器实例（SQLiteCredentialStoreManager）

| 属性 | 值 |
|------|-----|
| 单例语义 | 每个具体子类一个实例（基类 `__new__` 强制）；构造参数仅首次实例化生效，后续冲突参数抛 `ArgsException`（D8） |
| 事件循环 | 连接惰性创建并绑定首次使用时的 loop；跨 loop 操作抛 `ArgsException`（D7） |
| 内存态 | `dict[int, Credential]`（基类维护），与磁盘经 `store_data` 快照同步 |
| 生命周期 | `load()` 全量读入 → add / get / remove（auto_persist 时快照落盘）→ `close()` 显式关闭连接（实现附加 API） |

## 状态转换

```text
[无库文件] ──首次连接──▶ [空库 meta(schema_version=1)] ──add──▶ [N 条记录]
[已存在库] ──load()──▶ 内存字典全量恢复（按 order_seq）
add(新 uid) ──▶ 返回 True；add(旧 uid) ──▶ 覆盖、返回 False（order_seq 不变）
remove(uid) ──▶ 命中删行返回 True；未命中返回 False
任一 auto_persist ──▶ 单事务全量重写 credential 表（原子，FR-004）
落盘失败 ──▶ 异常抛出，内存态与上一次落盘数据均不变
close() ──▶ 连接关闭；实例不可再用于 IO（同 loop 内可重开新连接？否——close 后需重建实例）
```

## 校验规则汇总

| 规则 | 来源 | 失败行为 |
|------|------|----------|
| `credential.dedeuserid` 非空且 == `str(uid)` | 基类 `add_credential` | `ValueError` 原样传播，不落库 |
| `store_format` 标识匹配 | FR-008 / D3 | `CredentialStoreCorruptException` |
| `schema_version` 匹配 | FR-012 / D3 | `CredentialStoreVersionMismatchException` |
| GCM 认证标签校验 | D2 | 解密失败 → `CredentialStoreCorruptException` |
| RSA 私钥可解析 | FR-006 | `CredentialStoreCorruptException` |
| uid 与 order_seq 唯一性 | D6 | SQLite 约束兜底；正常路径不会触发 |
| 日志 / 异常消息零凭据值 | 宪章红线 / FR-008 / FR-013 | 实现保证 + 离线测试断言 |
