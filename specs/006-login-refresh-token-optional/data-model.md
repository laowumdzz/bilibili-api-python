# Data Model: 扫码登录不再强制 ac_time_value（refresh_token）非空

> Phase 1 输出。本特性不新增实体与文件格式，只重新定义既有实体 **登录凭据（Credential）** 的字段分层语义；TEMP 缓存记录与缓存校验状态机不变（沿用 specs/001 契约与 specs/003 data-model，此处仅登记分层影响）。

## 实体：登录凭据（Credential）

字段分层（本特性后的语义）：

| 层级 | 字段 | 语义 | 缺失 / 为空时的行为 |
|------|------|------|---------------------|
| 登录必需（WEB 扫码 DONE 分支校验） | `sessdata`、`bili_jct`、`dedeuserid` | 构成有效登录态的最小集合 | 抛 `ArgsException`（消息含字段名、不含值），登录不标记完成 |
| 可选-刷新材料 | `ac_time_value`（refresh_token） | 仅用于凭据过期刷新 | 登录照常成功；凭据该字段为空串；`has_ac_time_value()` 为 `False` |
| 可选-设备标识 | `buvid3`、`buvid4` | 设备指纹，机会性填充 | 缺失不影响登录与凭据可用性 |

### 字段校验矩阵（WEB 通道 check_state DONE 分支）

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 三 Cookie 齐全 + refresh_token 非空 | DONE，凭据六字段齐全 | 不变 |
| 三 Cookie 齐全 + refresh_token 缺失 | `ArgsException`（缺 ac_time_value） | DONE，凭据 ac_time_value 为 `""` |
| 三 Cookie 齐全 + refresh_token 为空串 | `ArgsException`（缺 ac_time_value） | DONE，凭据 ac_time_value 为 `""` |
| 任一 Cookie 缺失 / 空串（refresh_token 任意） | `ArgsException`（指明缺失字段名） | 不变 |
| refresh_token 非字符串真值（如数字） | `str(...)` 归一为字符串写入 | 不变 |

### 空值等价性约束（FR-003）

`ac_time_value` 的"空"在所有下游判定中三种表达等价（均为假值）：`None`、`""`、键缺失。锚点：

- `Credential.has_ac_time_value()`：`None` / `""` → `False`
- `Credential.get_cookies()` / `get_cached_cookies()`：假值统一映射为 `""`
- 缓存写入（`run_temp_login`）：仅保留非空字符串字段 → 空值不落盘
- 刷新材料判定（`check_cache`）：`not fields.get("ac_time_value")` → 三形态同走 `EXPIRED_NO_MATERIAL`

### 状态转移

无新增状态机。凭据生命周期不变：登录构造 →（校验有效 → 直接使用）｜（过期 + 有刷新材料 → 刷新回写）｜（过期 + 无刷新材料 → 删缓存回退）。本特性仅改变"构造"入口对 ac_time_value 的准入，不改任何转移条件。

## 实体：TEMP 登录缓存记录（不变，登记备查）

键集与必选性沿用 specs/001-pytest-temp-login/contracts/cache-file-format.md：`sessdata` / `bili_jct` / `dedeuserid` 必选，`ac_time_value` / `buvid3` / `buvid4` 可选。本特性后"无 ac_time_value 键"从边缘形态变为常规形态之一，合法性判定与既有测试（`tests/test_offline_login_cache.py`）不变。

## 实体：缓存校验状态机（不变，登记备查）

`CacheCheckStatus` 六态及转移条件沿用 specs/003-login-cache-script/data-model.md（E3），其中 `EXPIRED_NO_MATERIAL` 即"缺 ac_time_value 且过期"的既有终态，本特性使其触发频率上升但语义零变化。
