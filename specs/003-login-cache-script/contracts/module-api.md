# Contract: scripts.login_and_cache 模块导入面

**Date**: 2026-09-03 | **Status**: 已批准

`scripts/login_and_cache.py` 作为模块被 `tests/conftest.py` 与离线测试导入的公开面。导入机制依据：`tests/__init__.py` 使 pytest 将项目根插入 sys.path，`scripts/` 为命名空间包（无 `__init__.py`），见 [research.md](../research.md) R1。

## 供 conftest 导入

### 登录流程

```python
run_temp_login(
    login_type: str,                    # "qrcode" | "phone"
    *,
    notify: NotifyFn,                   # 注入输出回调（pytest terminal writer 包装）
    prompt: PromptFn,                   # 注入输入回调（真实 stdin 读取）
) -> dict[str, str] | None
```

- 成功 ⇒ 返回非空凭据字段集合（调用方不再负责写缓存——模块内部已写入并返回）。
- 任何中止 / 失败 ⇒ 返回 `None`（内部已输出经 `notify` 的中止原因，不写缓存）。
- 兼容基线：迁移前 conftest `_run_temp_login` 的全部中止分支（`_LoginAbort` / KeyboardInterrupt / EOFError / Exception）语义与提示文本不变。

### 缓存校验 / 刷新（富结果状态机）

```python
class CacheCheckStatus(enum.Enum):      # 终态：见 data-model.md E3
    VALID = ...                         # 缓存有效
    REFRESHED = ...                     # 过期已刷新并回写（fields 为刷新后字段）
    EXPIRED_NO_MATERIAL = ...           # 过期且缺 ac_time_value（缓存文件已删除）
    REFRESH_FAILED = ...                # 过期且刷新失败（缓存文件已删除）
    NETWORK_ERROR = ...                 # 有效性无法验证（缓存文件保留）
    NO_CACHE = ...                      # 无缓存可用

@dataclass
class CacheCheckResult:
    status: CacheCheckStatus
    fields: dict[str, str]              # VALID / REFRESHED 时非空，其余为空 dict

check_cache(
    fields: dict[str, str] | None,
    *,
    notify: NotifyFn,
) -> CacheCheckResult
```

- 联网动作（`check_valid` / `refresh`）在独立事件循环中执行并关闭请求客户端会话（沿用现状 `_check_cache_valid` / `_refresh_credential` 语义）。
- conftest 映射：`NETWORK_ERROR` ⇒ `pytest.skip`（保留缓存）；`EXPIRED_NO_MATERIAL` / `REFRESH_FAILED` ⇒ `warnings.warn`（文件已由模块删除）；`NO_CACHE` ⇒ 回退链续行。

### 纯函数 re-export

`login_and_cache` re-export `scripts/_login_cache.py` 的全部公开名（`get_cache_path` / `load_cache` / `save_cache` / `encode_credential_cache` / `merge_credential_values` / `CacheStatus` / `CacheLoadResult` / `CACHE_FIELDS` / `REQUIRED_FIELDS` / `CACHE_FILENAME`），conftest 可单点导入。

## 供离线测试导入

```python
from scripts._login_cache import ...    # 纯逻辑模块：不导入 bilibili_api，无网络副作用
```

- `scripts/_login_cache.py` 为 `tests/_login_cache.py` 的原样平移（内容零改动）；`test_offline_login_cache.py` 仅改此导入行，纯度不变量（文件头声明的"不导入 bilibili_api"）保持。

## I/O 接缝类型

```python
NotifyFn = Callable[[str], None]        # 实现方自行承载 error 标记语义（脚本侧写 stderr）
PromptFn = Callable[[str], str]         # 显示提示后读一行，返回去首尾空白前的原始行
```

- 独立运行时的缺省实现：notify ⇒ stdout（错误 ⇒ stderr），prompt ⇒ stdout 提示 + `input()` 读取；EOF ⇒ 按中止语义处理（退出码 1）。
- conftest 注入实现：现有 `_notify` / `_prompt`（terminal writer + 原始 stdin 回退），提示语义与迁移前一致。

## 不属于公开面的部分

`_qrcode_login_flow` / `_phone_login_flow` / 极验辅助 / `main()` 等模块内部实现，conftest 与测试不得直接依赖；其行为仅经 CLI 契约（[cli.md](cli.md)）与 `run_temp_login` 间接验收。
