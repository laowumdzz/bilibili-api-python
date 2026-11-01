# Implementation Plan: 基于 aiosqlite 的凭据存储管理器实现

**Branch**: `011-aiosqlite-credential-store` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-aiosqlite-credential-store/spec.md`

## Summary

为 `bilibili_api/utils/credential_store.py` 的抽象基类 `BaseCredentialStoreManager` 提供 aiosqlite 具体实现类（`SQLiteCredentialStoreManager`）：凭据按 UID 落盘单文件 SQLite 数据库，插入顺序跨进程保持；落盘内容经 RSA-2048（pycryptodomex）混合 AES-256-GCM 静态加密，密钥对随机生成仅存本地；默认位置为 platformdirs 解析的 OS 标准应用数据目录，路径可覆盖。schema 版本不匹配、库损坏、密钥丢失均显式报错（项目自定义异常）。前置依赖：完成工作区中 `Credential` 的 pydantic 化（当前构造即抛错，已验证最小修复模式可行，见 research.md D1）。

## Technical Context

**Language/Version**: Python ≥ 3.10（兼容 CPython 3.10，CI 跑 3.10 / 3.13）

**Primary Dependencies**: aiosqlite>=0.22.1（既有，本特性首次启用）；pycryptodomex（既有，RSA-2048-OAEP + AES-256-GCM）；pydantic>=2.14.2（既有，Credential 序列化）；platformdirs>=4.0（**新增**，经 `uv add` 引入，默认存储位置解析）

**Storage**: 本地单文件 SQLite 数据库（经 aiosqlite 异步访问）+ RSA-2048 密钥文件（PEM），两者同目录、可自定义路径

**Testing**: pytest 离线用例（`tests/test_offline_credential_store_sqlite.py`），禁外网 / 真实凭据；合入门禁 `uv run python scripts/lint.py`

**Target Platform**: Windows（开发环境）+ POSIX（CI 3.10 / 3.13），路径行为一致

**Project Type**: library（`bilibili_api` 内新增一个存储模块，无 CLI / 服务）

**Performance Goals**: 单条凭据增 / 覆盖 / 移除（含落盘）≤ 1 秒；50 账号全量 load ≤ 3 秒（SC-004）

**Constraints**: 异步优先（宪法 I，禁止同步阻塞 IO / `asyncio.run()`）；凭据字段值不得出现在任何日志 / 错误 / 落盘明文中（宪法凭据安全红线）；存储文件与密钥文件必须 gitignore；不依赖 NoneBot 运行时

**Scale/Scope**: 单进程、数十账号量级（验收按 50 账号）；1 个实现类 + 1 个前置修复（Credential）+ 3 个异常类 + 1 个离线测试文件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. 异步优先 | ✅ | 所有公共方法 `async def`；aiosqlite 天然异步；连接惰性创建并绑定事件循环（与基类"同一 loop"约定一致）；库代码无 `asyncio.run()` |
| II. 声明式 API 定义 | ✅（不适用） | 本特性不调用任何 B 站接口，不新增 `data/api/*.json` 条目，不触碰 registry 同步链路 |
| III. 质量门禁 | ✅ | 全量类型注解 + 中文 docstring（Args / Returns / Raises）；不引入类型豁免；合入前跑 `scripts/lint.py` 并以 mypy==1.18.2 重新生成 `docs/modules/` |
| IV. 分层测试 | ✅ | 仅离线用例（`tests/test_offline_*.py`）：本地临时目录文件 IO 属本机操作，无外网、无真实凭据、不改账号状态；不新增需凭据 marker |
| V. 兼容性与破坏性变更 | ✅ | 新增实现类为纯增量；`Credential` 修复保持 `__init__` 签名与既有语义（URL 编码 sessdata、proxy、**kwargs）不变，非破坏性；新依赖 platformdirs 经 uv 管理；异常用 `bilibili_api/exceptions/` 自定义类，不裸 `raise Exception` |
| 凭据安全红线 | ✅ | 落盘静态加密（FR-005）；存储文件 / 密钥文件加入 .gitignore（FR-007）；日志与异常信息零凭据值（FR-008 / FR-013） |

**Post-Design Re-check**: Phase 1 设计未引入宪章冲突——加密采用既有依赖 pycryptodomex（未新增加密栈）；事务化快照持久化满足原子性；见 research.md D2–D9。无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/011-aiosqlite-credential-store/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
│   └── credential-store-api.md
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
bilibili_api/
├── utils/
│   ├── credential_store.py             # 既有抽象基类（本特性不改动）
│   └── credential_store_sqlite.py      # 新增：SQLiteCredentialStoreManager 实现类
├── exceptions/
│   ├── CredentialStoreException.py             # 新增：基类（ApiException 子类）
│   ├── CredentialStoreCorruptException.py      # 新增：库损坏 / 解密失败 / 密钥丢失损坏
│   └── CredentialStoreVersionMismatchException.py  # 新增：schema 版本不匹配
└── utils/_credential.py                # 前置修复：Credential 声明 pydantic 字段 + extra='allow'（D1）

tests/
└── test_offline_credential_store_sqlite.py     # 新增：离线测试（唯一测试文件）

pyproject.toml / uv.lock                # uv add platformdirs
.gitignore                              # 追加存储文件与密钥文件名兜底条目
```

**Structure Decision**: 单项目库布局，实现类与基类同层（`bilibili_api/utils/`），异常按仓库惯例一文件一类；不新增子包。

## Complexity Tracking

> 无宪章违规项，本节留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| （无） | — | — |
