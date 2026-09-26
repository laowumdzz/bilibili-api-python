# Contract: QrCodeLogin WEB 通道凭据构造（library-api）

> Phase 1 输出。本契约定义本特性对库公共行为面的**变更边界**；`scripts/login_and_cache.py` 的 CLI / 模块契约（specs/003/contracts/cli.md、module-api.md）与缓存文件契约（specs/001/contracts/cache-file-format.md）经核实均不受影响，此处仅引用不变。

## `QrCodeLogin.check_state()` —— WEB 通道 DONE 分支（变更）

### 凭据构造规则

登录成功（轮询 code 非 86101 / 86090 / 86038）时，凭据字段来源与必需性：

| 字段 | 来源 | 必需性 |
|------|------|--------|
| `sessdata` / `bili_jct` / `dedeuserid` / `buvid3` / `buvid4` | 本响应 Set-Cookie 标头（字段名匹配不区分大小写；未映射 Cookie 忽略；值原样保留不二次解码） | 前三者**必需**：缺失或为空串 → 抛 `ArgsException`；buvid 两项机会性填充 |
| `ac_time_value` | 响应体 `refresh_token` 字段 | **可选**：缺失或为空 → 不抛异常，凭据该字段为空串 `""`；非空真值经 `str()` 归一后写入 |

### 异常契约

- `ArgsException`：仅当 SESSDATA / bili_jct / DedeUserID 任一缺失或为空串时抛出。消息**只含缺失字段名**（逗号连接），不含任何 Cookie / token 值；抛出时登录不标记完成（`has_done()` 为 `False`，`get_credential()` 继续抛 `StatementException`）。
- 修改前"缺 refresh_token 抛 ArgsException"的行为废止（修订 specs/002 FR-001 / FR-004 的对应约定）。

### 幂等性与状态判定（不变）

- 86101 → SCAN、86090 → CONF、86038 → TIMEOUT 的判定不变；DONE 后重复轮询幂等，凭据不清空不改写。

## 不变面（引用锁定）

- `QrCodeLogin` TV 通道：凭据仍从结构化 `data.cookie_info` 构造，无必需字段校验，行为不变。
- 短信登录（`login_with_sms`，含 `LoginCheck` 风控二次验证）与密码登录：凭据构造不对 ac_time_value 做非空阻断，行为不变。
- `Credential` 公共接口：无签名变化；`has_ac_time_value()` / `raise_for_no_ac_time_value()` 等既有假值语义不变。
- `scripts/login_and_cache.py`：`run_temp_login`（成功写缓存、仅落非空字段）、`check_cache` 六态状态机（含 `EXPIRED_NO_MATERIAL`）、CLI 退出码契约均不变——ac_time_value 为空的登录在其中的表现：缓存缺该键、校验通过直接使用、过期删缓存回退。

## 版本语义

行为放宽（原异常路径改为成功路径），无接口签名 / 返回类型变化，属非破坏性变更；`docs/modules/` 中 login_v2 文档随 docstring 再生成同步。
