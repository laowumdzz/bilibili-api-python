# Data Model: pytest 临时登录凭据（--login）

**Date**: 2026-08-31 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## 实体

### 1. LoginCredentialCache（临时凭据缓存文件）

磁盘上的单一文件，承载跨次测试运行的临时登录凭据。

| 字段/属性 | 说明 |
|----------|------|
| 路径 | `tempfile.gettempdir()` 下固定名称（见 [contracts/cache-file-format.md](contracts/cache-file-format.md)） |
| 编码 | `base64(UTF-8 JSON 对象)` |
| JSON 键 | `sessdata`、`bili_jct`、`buvid3`、`buvid4`、`dedeuserid`、`ac_time_value`（全部 `str`，可缺省） |
| 必需键 | `sessdata`、`bili_jct`、`dedeuserid`（空串等同缺失） |
| 关系 | 由 LoginSession 成功后写入；由 CredentialResolver 读取/覆盖/删除 |

**校验规则**（任一失败 → 状态 = `corrupt`）：
1. 文件可读且非空
2. base64 可解码
3. 解码结果为合法 UTF-8 JSON，顶层为对象
4. 三个必需键齐全且非空

**生命周期 / 状态机**：

```text
             写入(LoginSession 成功)
 absent ─────────────────────────────▶ valid_or_stale
    ▲                                        │ 读取并校验
    │  删除(corrupt)                          ├─ 校验失败 ──▶ corrupt ──删除──▶ absent
    │  删除(refresh_failed)                   ├─ check_valid()=True ─▶ usable（直接使用）
    │                                         └─ check_valid()=False ─▶ stale
    │                                                              │
    │                                              refresh() 成功 ──┤ 回写缓存 → usable
    └──────────────────────────────── refresh() 失败 / 无刷新材料 ──┘
```

补充态 `unverifiable`：`check_valid()` 因网络异常无法完成——保持文件原状（不删除），本次运行跳过凭据测试。

### 2. LoginSession（临时登录会话）

由 `--login <type>` 触发的一次性交互过程，产物为内存中的 `Credential`。

| 属性 | 取值 |
|------|------|
| type | `qrcode` \| `phone` |
| 平台复用 | `QrCodeLogin`（WEB）\| `Geetest` + `send_sms` + `login_with_sms`（+ `LoginCheck` 二次验证分支） |
| 终态 | `succeeded`（返回凭据并写缓存）\| `aborted`（用户中断 / 二维码连续 3 次超时 / 短信流程失败——提示后不写缓存） |

**状态转移**：

- qrcode：`生成二维码 → 展示 → 轮询(SCAN/CONF→等待, TIMEOUT→续期, 计数=3 则 aborted, DONE→succeeded)`
- phone：`输入手机号 → 极验(本地服务+浏览器完成) → 发送短信 → 输入验证码 → 登录 → (LoginCheck? 二次验证) → succeeded | aborted`

### 3. CredentialSource（凭据来源优先级链）

conftest 解析登录态时的有序来源列表（resolve 顺序即优先级，首个可用者胜出）：

| 优先级 | 来源 | 可用性条件 |
|-------|------|-----------|
| 1 | 本次 `--login` 登录所得 | 会话 `succeeded` |
| 2 | TEMP 缓存 | 状态为 `usable`（含刷新成功后回写的情形） |
| 3 | `BILI_*` 环境变量 | 现行 `_load_credential_values()` 语义不变 |
| 4 | `.bilibili.cookie` 文件 | 现行语义不变 |

全部不可用 → `pytest.skip`（沿用现行 skip 文案风格）。缓存处于 `corrupt` / `stale(刷新失败)` 时按各自路径输出反馈并删除文件，随后**继续走 3→4 回退**——仅当回退也为空时才 skip。

## 验证规则汇总（映射 spec FR）

| 规则 | 来源 FR |
|------|--------|
| 必需字段齐全才算「内容正确」 | FR-008 |
| 消息/日志/异常中不得出现凭据字段值 | FR-014 |
| 二维码连续 3 次 TIMEOUT 中止且不写缓存 | FR-003 |
| 刷新成功回写缓存 | FR-011 |
| 网络异常无法验证 → 不删除文件 | FR-013 |
| 无 `--login` 且缓存缺失时行为与引入前一致 | FR-017 / SC-005 |
