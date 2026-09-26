# Research: 扫码登录不再强制 ac_time_value（refresh_token）非空

> Phase 0 输出。技术上下文无 NEEDS CLARIFICATION 项，全部结论来自源码核实（2026-09-26），按"决策 / 依据 / 已拒替代方案"组织。

## D1 判断点定位：脚本无判断，实际在上游登录实现

- **Decision**: 改动落在 `bilibili_api/login_v2.py` 的 `QrCodeLogin.check_state()` WEB 通道 DONE 分支（当前 538-542 行的 `missing` 必需字段元组），不在 `scripts/login_and_cache.py`。
- **依据**: 脚本自身对 ac_time_value 无任何非空判断（`run_temp_login` 仅做"仅保留非空字符串"过滤后写缓存）；其扫码流程经 `check_state()` → DONE → `get_credential()` 感受该异常，`run_temp_login` 的兜底 `except Exception` 捕获后整体判"临时登录失败"、不写缓存。
- **已拒替代方案**: 在脚本层 try/except 掩盖该异常——治标不治本，库使用者直连 `QrCodeLogin` 仍会失败，且会把"Cookie 真缺失"与"仅缺 refresh_token"混为同一失败形态。

## D2 改动方案：必需字段元组移除 ac_time_value，归一逻辑保持

- **Decision**: `missing` 判定元组从 `("sessdata", "bili_jct", "dedeuserid", "ac_time_value")` 收窄为 `("sessdata", "bili_jct", "dedeuserid")`；`kwargs` 的 `ac_time_value` 归一表达式 `str(events.get("refresh_token") or "")` 原样保留（缺失/空 → 空串）。
- **依据**: 最小 diff；refresh_token 存在且非空时的写入路径完全不受影响（FR-002）；三 Cookie 缺失的 `ArgsException` 契约（消息含字段名、不含凭据值、`has_done()` 保持 False）原样保留。
- **已拒替代方案**:
  - 空→`None` 归一：多改一处且与"服务端下发空串"的现状表达不一致，收益为零（见 D3 等价性）。
  - 给 `check_state` 加 `strict_fields` 开关参数：扩大公共 API 面，违背"新增参数优先带默认值、避免无谓 API 膨胀"的项目取向，且无真实用例需要旧行为。

## D3 空值形态：保留空串，链路行为与 None 天然等价

- **Decision**: ac_time_value 为空时统一表达为空字符串 `""`，不引入 `None` 分支。
- **依据**（逐环节核实）:
  - `Credential.__init__` 形参类型即 `str | None = None`（`bilibili_api/utils/_credential.py:54`），两形态均可构造。
  - `Credential.has_ac_time_value()`（178-185 行）对 `None` 与 `""` 一律返回 `False`；`get_cookies()` / `get_cached_cookies()` 将假值统一映射为 `""`。
  - `scripts/login_and_cache.py` 的 `run_temp_login` 仅保留非空字符串字段 → 缓存文件永不出现空值 ac_time_value 键。
  - `check_cache` 的刷新材料判定 `if not fields.get("ac_time_value")` 为真值判定 → `""` / 缺键 / `None` 三者同走 `EXPIRED_NO_MATERIAL`。
- **已拒替代方案**: 在凭据层新增"规范化为 None"的工具方法——无行为差异，纯代码洁癖，不值得新增公共面。

## D4 缓存链路零改动的依据

- **Decision**: `scripts/_login_cache.py`、`scripts/login_and_cache.py`、`tests/conftest.py` 均不改；其行为由既有离线用例与 003 契约锁定为回归对象。
- **依据**:
  - 缓存合法性判定中 ac_time_value 本就是可选字段（`tests/test_offline_login_cache.py:161` 明确锁定"可选键缺失不影响合法性"）。
  - `check_cache` 状态机的 `EXPIRED_NO_MATERIAL` 分支即是为"缺 ac_time_value 且过期"设计的终态（删缓存文件 + conftest 警告跳过），空值常态化后语义严丝合缝。
  - 有效期内校验 `check_valid()` 不依赖 ac_time_value（走导航类只读接口），空值不影响判定。
- **已拒替代方案**: 顺带把 `EXPIRED_NO_MATERIAL` 改为保留缓存文件——超出本特性范围（属缓存清理策略变更），且会破坏 003 契约与 conftest 映射。

## D5 测试影响面与形态

- **Decision**:
  1. 反转 `test_check_state_web_missing_refresh_token_raises`（`tests/test_offline_login_v2.py:218`）为断言新行为：缺 refresh_token → `DONE`、凭据可取得、三 Cookie 非空、`ac_time_value == ""`、`has_ac_time_value() is False`。
  2. 新增 refresh_token 为空串的场景用例（缺失与空串两形态，覆盖 Edge Case 第 1 条）。
  3. 同步微调 `test_check_state_web_done_builds_credential_from_set_cookies` 的 docstring 措辞（"四项必需字段"→ 三项必需 + 可选 refresh_token），断言不变。
  4. 其余用例零改动：缺 Cookie 报错（`test_check_state_web_missing_cookie_raises` / `test_check_state_web_empty_cookie_value_raises`）、TV 通道、三状态判定、幂等、缓存链路用例照旧通过。
- **依据**: 复用 `_make_qrcode_login` / `_patch_web_poll(events, cookies)` / `_FULL_FAKE_COOKIES` 既有辅助，全部离线、fake 值，不触网。
- **已拒替代方案**: 新建独立测试文件——用例与既有 check_state 套件强内聚，拆分徒增导航成本。

## D6 文档联动义务（宪法 III）

- **Decision**: `check_state` docstring 的 Raises 段（当前 502 行）必须从四字段表述改为三字段 + "ac_time_value 为可选，缺失/为空时凭据该字段为空串、不报错"；随后重跑 `uv run python scripts/doc_gen.py`，`docs/modules/` 由工具再生成。
- **依据**: lint 门禁的文档漂移校验以 docstring 为单一事实源，公共方法 docstring 与 `docs/modules/` 漂移会被阻断；手改 `docs/` 为宪法明令禁止。
- **已拒替代方案**: 只改代码不改 docstring——门禁必挂，且公共行为变更不落文档违反项目规范。

## D7 跨规格关系

- **Decision**: specs/002-qrcode-login-cookie-fix 的 FR-001 / FR-004（四字段必需、缺任一报错）被本特性显式修订，历史规格文件保持原样不动（它们是当时决策的记录）；修订关系已在 specs/006 spec.md 头部声明。
- **依据**: specs/001（缓存文件契约）、specs/003（login_and_cache 行为契约 cli.md / module-api.md）经核实均不含"登录成功必须带 ac_time_value"的表述，无需联动修订。
- **已拒替代方案**: 回写修订 specs/002 正文——篡改历史规格会让 002 的验收记录失去语境，spec-kit 实践是以新特性声明修订。
