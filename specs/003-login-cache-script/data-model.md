# Phase 1 Data Model: 测试登录凭证流程迁移至独立脚本

**Date**: 2026-09-03 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

本特性为迁移型变更：数据实体与缓存契约全部沿用现状，零schema变更。此处记录迁移后各实体归属与状态机，作为任务分解与验收对照。

## 实体清单

### E1: 登录凭据字段集合（CredentialFieldSet）

| 属性 | 值 | 归属 |
|------|----|----|
| 字段集 | `sessdata` / `bili_jct` / `dedeuserid` / `ac_time_value` / `buvid3` / `buvid4`（均 str） | `scripts/_login_cache.py`（`CACHE_FIELDS`，平移不变） |
| 必需字段 | `sessdata` / `bili_jct` / `dedeuserid`（任一缺失即内容不合法） | `scripts/_login_cache.py`（`REQUIRED_FIELDS`，平移不变） |
| 来源 | 扫码登录成功 ⇒ `QrCodeLogin.get_credential()`；短信登录成功 ⇒ `login_with_sms` / `LoginCheck.complete_check()` 返回的 `Credential` | `scripts/login_and_cache.py` |
| 提取规则 | `Credential` 六字段中非 None 非空串者入选（现状 `_credential_to_fields` 语义） | `scripts/login_and_cache.py` |

### E2: 凭据缓存文件（CacheFile）

- **路径**: `tempfile.gettempdir() / bilibili_api_pytest_login.json`（`get_cache_path()`，固定名，同机后一次覆盖前一次）
- **格式**: base64(UTF-8 JSON) 单行 ASCII；契约见 [specs/001-pytest-temp-login/contracts/cache-file-format.md](../001-pytest-temp-login/contracts/cache-file-format.md)，**本特性不变更**
- **读取三态**（`load_cache` → `CacheLoadResult`，平移不变）: `ABSENT`（缺失）/ `CORRUPT`（内容不对，含原因描述）/ `OK`（合法，含字段集）

### E3: 缓存校验/刷新状态机（CacheValidationOutcome，新增收敛）

迁移动作：把 conftest `_resolve_cache_usable_fields` 的"逻辑"收敛为脚本模块的富结果状态机，pytest 副作用（skip / warn）留在 conftest 映射。

```text
        ┌──────────── cache_fields 为 None ───────────► 不可用（回退环境变量/cookie）
输入 ──►│
        └─► check_valid() 联网校验
             ├─ 网络异常 ──────────────────────────► NETWORK_ERROR（保留缓存文件；conftest 映射 skip）
             ├─ 有效 ─────────────────────────────► VALID（使用缓存字段）
             └─ 过期
                 ├─ 缺 ac_time_value ──────────────► EXPIRED_NO_MATERIAL（删缓存文件；conftest 映射 warn）
                 └─ 含 ac_time_value → refresh()
                     ├─ 失败 ──────────────────────► REFRESH_FAILED（删缓存文件；conftest 映射 warn）
                     └─ 成功 ─► 回写缓存文件 ──────► REFRESHED（使用刷新后字段）
```

- 每个终态附用户可读消息（不含凭据值）；两入口（conftest / 独立脚本）共享同一状态机与消息语义（US3 验收依据）。

### E4: 凭据来源回退链（CredentialSourceChain，语义不变）

优先级从高到低（现状不变，仅实现位置变化）：

1. `--login` / 脚本登录的新凭据（登录成功时已同步写缓存）
2. TEMP 缓存（经 E3 状态机校验/刷新）
3. `BILI_*` 环境变量
4. 项目根 `.bilibili.cookie` 文件

字段级合并：高优先级字段落定后低优先级不覆盖（`merge_credential_values`，平移不变）；必需三键不全 ⇒ 整链不可用 ⇒ conftest skip。

### E5: 登录流程状态（LoginFlow，行为不变）

**扫码流程**（`_qrcode_login_flow` 迁移体）：`生成二维码 → 轮询(2s)`；事件映射：`CONF`（首次提示确认）→ `DONE`（返回 Credential）/ `TIMEOUT`（重生成，连续 3 次中止）/ 其他（继续）；终端渲染失败回退 TEMP 图片路径提示。

**短信流程**（`_phone_login_flow` 迁移体）：`地区码(默认+86)/手机号输入 → 极验滑块(浏览器完成, 0.5s 轮询) → send_sms → 验证码输入 → login_with_sms`；`LoginCheck` 分支 ⇒ 二次极验 → 二次短信 → `complete_check`。

**中止语义**（不变）：用户中断（Ctrl+C）/ 连续超时 / 流程失败 / EOF ⇒ 中止原因（不含凭据值）+ 不写缓存 + 既有缓存不动。

## 校验规则汇总（迁移前后一致性对照）

| 规则 | 迁移前位置 | 迁移后位置 | 变化 |
|------|-----------|-----------|------|
| 缓存路径/编码/三态判定 | `tests/_login_cache.py` | `scripts/_login_cache.py` | 无（原样平移） |
| 来源优先级合并 | `tests/_login_cache.py` | `scripts/_login_cache.py` | 无（原样平移） |
| 二维码/短信/极验流程 | `tests/conftest.py` | `scripts/login_and_cache.py` | 无（I/O 经接缝注入，见 research R3） |
| 缓存联网校验+刷新+回写 | `tests/conftest.py` | `scripts/login_and_cache.py`（E3 状态机） | 逻辑收敛，UX 映射拆到调用方 |
| 凭据装配与回退链 | `tests/conftest.py` | `tests/conftest.py` | 无（保留） |
| 限速 / 超时设置 | `tests/conftest.py` | `tests/conftest.py` | 无（保留） |
