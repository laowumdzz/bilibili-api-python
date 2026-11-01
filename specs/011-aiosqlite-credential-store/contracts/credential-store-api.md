# API Contract: SQLiteCredentialStoreManager

**Feature**: `011-aiosqlite-credential-store` | **Date**: 2026-11-01

本库对下游暴露的公共 Python 接口契约。所有签名以本文档为准；实现须提供完整类型注解与中文 docstring（宪法 III）。

## 模块与导入

```python
from bilibili_api.utils.credential_store_sqlite import SQLiteCredentialStoreManager
from bilibili_api.exceptions import (
    CredentialStoreException,                      # 存储模块异常基类
    CredentialStoreCorruptException,               # 库损坏 / 解密失败 / 密钥丢失或损坏
    CredentialStoreVersionMismatchException,       # schema 版本不匹配
)
```

三个异常均继承既有 `ApiException`；异常消息只含文件路径与原因类别，不含凭据字段值。

## 类定义

```python
class SQLiteCredentialStoreManager(BaseCredentialStoreManager):
    def __init__(self, db_path: str | Path | None = None, key_path: str | Path | None = None) -> None: ...
```

**构造语义（D8）**：
- 每个具体子类单例（基类强制）。`db_path` / `key_path` 仅**首次实例化**生效；`None` 时解析默认值（D4）：
  - 目录：`platformdirs.user_data_dir("bilibili-api", appauthor=False)`，不存在则惰性创建；
  - 文件：目录下 `credentials.db` 与 `credentials.key`。
- 后续再次实例化时：无参 / 同值参数 → 返回单例；与已配置不同的路径 → `ArgsException`。

**继承的公共 API（语义不变，FR-002）**：

| 方法 | 契约要点 |
|------|----------|
| `async def add_credential(uid: int, credential: Credential, auto_persist: bool = True) -> bool` | uid 与 `dedeuserid` 一致性校验（不一致 `ValueError`）；新 uid 返回 True，覆盖返回 False；auto_persist 时快照落盘 |
| `async def get_credential(uid: int | None = None) -> Credential | None` | uid=None 返回**插入顺序最早**的一条（order_seq 升序，FR-003）；命中返回深拷贝 |
| `async def remove_credential(uid: int, auto_persist: bool = True) -> bool` | 命中删除返回 True，未命中 False |
| `async def get_all_uids() -> list[int]` | 按 order_seq 升序返回全部 uid |
| `classmethod async def load(cls) -> Self` | 全量读盘恢复内存态；内部经 `cls()` 单例复用配置与连接 |
| `classmethod async def read_data(cls) -> dict[int, Credential]` | 抽象方法实现：读出全部记录（按 order_seq），不校验凭据有效性（基类契约） |
| `async def store_data(credentials: dict[int, Credential]) -> None` | 抽象方法实现：单事务内全量重写 credential 表（原子，FR-004）；失败抛异常且不破坏上一次落盘数据 |
| `__len__() -> int` | 内存态条数（同步，基类既有） |

## 实现附加 API

| 方法 | 契约 |
|------|------|
| `async def close() -> None` | 显式关闭数据库连接（实现附加，基类无此 API）；关闭后实例不可再用于 IO；幂等 |
| `@property db_path -> Path` | 实际生效的数据库文件路径（默认解析后的绝对路径） |
| `@property key_path -> Path` | 实际生效的密钥文件路径 |

## 异常契约

| 场景 | 异常 | 消息允许内容 |
|------|------|--------------|
| 库文件损坏 / 截断 / 非本库格式（store_format 不符） | `CredentialStoreCorruptException` | 路径 + "损坏或非本库格式"类别描述 |
| GCM 认证失败 / 解密失败 | `CredentialStoreCorruptException` | 路径 + "解密失败"类别描述 |
| 密钥文件缺失或 PEM 解析失败 | `CredentialStoreCorruptException` | 路径 + "密钥不可用，需重新添加账号"类别描述 |
| `schema_version` 高于 / 低于实现已知版本 | `CredentialStoreVersionMismatchException` | 双方版本号 + 升级提示 |
| 跨事件循环使用实例 | `ArgsException` | loop 不一致描述（不含凭据） |
| 后续实例化传入冲突路径 | `ArgsException` | 配置冲突描述 |
| uid 与 dedeuserid 不一致 | `ValueError`（基类既有） | 基类既有行为，原样传播 |
| 磁盘 / 权限等 IO 失败 | 原生 `OSError` 原样传播（不包装、不吞并），且 MUST 先回滚内存态再抛（FR-004） | 不含凭据 |

**首次使用语义**：库文件或密钥文件不存在 → 视为空库 / 新钥，正常创建（Edge Case，不报错）；密钥文件存在但损坏 → `CredentialStoreCorruptException`，不静默重建（FR-006）。

## 并发与生命周期契约

- 所有 IO 方法为 `async`；连接绑定首次使用的事件循环，跨 loop 抛 `ArgsException`（D7）。
- 写持久化由基类 `_persist_lock` 串行化；`store_data` 事务保证落盘原子性。
- 不承诺跨进程并发写同一库文件（spec Assumptions；SQLite 事务为兜底）。
- Python 3.10 兼容；不使用 3.10 以上独有特性。

## 行为示例（验收口径）

```python
store = SQLiteCredentialStoreManager(db_path=tmp / "credentials.db", key_path=tmp / "credentials.key")
await store.load()                                    # 空库 → len == 0
is_new = await store.add_credential(100, Credential(sessdata="s1", bili_jct="j1", dedeuserid="100"))
assert is_new is True                                 # 新 uid
await store.add_credential(5, Credential(..., dedeuserid="5"))
first = await store.get_credential()                  # → uid=100 的凭据（先添加者，即使 uid 数值更大）
```
