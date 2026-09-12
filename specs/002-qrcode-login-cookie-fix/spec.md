# Feature Specification: 修复网页端二维码登录凭据获取失效

**Feature Branch**: `002-qrcode-login-cookie-fix`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "目前的二维码登录有一个错误，在 login_v2.py 的 489 到 501 行获取 cookies_list 的逻辑现在失效了，原因在于 get_events(web/qrcode/poll) 这个 API 它不返回带有 cookie 的 url，实测响应中的 url 是 passport.biligame.com 的 crossDomain 跳转链接（查询串不含 Cookie），它的 cookies_list 实际在响应标头 Set-Cookie 部分（一共 5 个）。后面实例化 Credential 时 sessdata、bili_jct、dedeuserid 变量为空，导致无法形成有效 Credential。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 扫码确认后获得可用登录凭据 (Priority: P1)

库使用者通过 `QrCodeLogin`（WEB 通道）生成二维码并在终端展示，用手机 B 站 App 扫码并在手机上确认登录。此后轮询 `check_state()`，当服务端判定登录成功时，使用者调用 `get_credential()` 应得到一个字段完整、可正常使用的登录凭据。

**Why this priority**: 这是二维码登录的核心价值交付。当前缺陷使该主流程完全不可用——登录状态被误判为成功（返回 DONE），但凭据中 SESSDATA、bili_jct、DedeUserID 均为空字符串，后续所有需要登录态的调用静默失败。修复它是本特性的全部意义。

**Independent Test**: 生成二维码 → 真机扫码并确认 → 轮询至 DONE → 检查 `get_credential()` 返回的凭据中 SESSDATA、bili_jct、DedeUserID、ac_time_value 全部非空，并用它调用任一需登录态的只读接口验证身份被识别。

**Acceptance Scenarios**:

1. **Given** 已生成网页端二维码且用户已在手机上确认登录，**When** `check_state()` 轮询到服务端判定登录成功，**Then** 返回 `QrCodeLoginEvents.DONE`，且 `get_credential()` 得到的凭据中 SESSDATA、bili_jct、DedeUserID、ac_time_value 全部非空。
2. **Given** 持有上述登录成功的凭据，**When** 调用任一需要登录态的只读接口，**Then** 服务端将其识别为已登录用户（不再视作游客）。
3. **Given** 登录成功后再次轮询 `check_state()`，**When** 使用同一 qrcode_key，**Then** 凭据内容保持一致，不因重复轮询被清空或改写为无效值。

---

### User Story 2 - 凭据不完整时明确报错 (Priority: P2)

当服务端响应未按预期下发构造有效凭据所必需的 Cookie（例如缺少 SESSDATA 或 bili_jct）时，登录流程应以项目异常体系中的明确异常终止，而不是静默构造一个字段为空的凭据并把登录状态判为成功。

**Why this priority**: 当前失败模式是"假成功"——状态返回 DONE 但凭据不可用，使用者要到后续业务调用失败时才能发现，排障成本高。明确的失败信号让问题在登录现场暴露，是可诊断性的关键。

**Independent Test**: 以构造的模拟响应（缺少任一必需 Cookie）驱动凭据提取逻辑（离线单元测试，无需真机），断言抛出明确的参数类异常且异常消息指明缺失的字段名。

**Acceptance Scenarios**:

1. **Given** 轮询响应被判定为登录成功但必需 Cookie 缺失任一项，**When** 执行凭据构造，**Then** 抛出项目异常体系中的参数类异常，异常消息指明缺失字段名。
2. **Given** 上述异常抛出场景，**When** 检查异常消息与日志，**Then** 其中不包含任何 Cookie 字段的实际值，只有字段名与状态描述。
3. **Given** 凭据构造失败，**When** 使用者查看登录对象状态，**Then** 登录不被标记为已完成（不会出现"返回 DONE 但凭据为空"的组合）。

---

### User Story 3 - 既有登录流程无回归 (Priority: P3)

本次修复不得改变二维码登录其余环节的既有行为：未扫码（SCAN）、已扫码未确认（CONF）、二维码过期（TIMEOUT）三种状态的判定，以及 TV 通道二维码登录的完整流程，均须与现状保持一致。

**Why this priority**: 修复不能以破坏正常功能为代价。状态判定与 TV 通道是同一代码路径上的邻接逻辑，必须被显式保护，防止修复引入新问题。

**Independent Test**: 离线单元测试分别模拟 code 86101 / 86090 / 86038 的响应，断言状态判定不变；TV 通道用例（模拟结构化 cookie_info 响应）断言凭据构造逻辑不变，全部无需真机。

**Acceptance Scenarios**:

1. **Given** 二维码已生成但未被扫码，**When** 轮询 `check_state()` 得到 code 86101，**Then** 返回 `QrCodeLoginEvents.SCAN`。
2. **Given** 已扫码但未在手机上确认，**When** 轮询得到 code 86090，**Then** 返回 `QrCodeLoginEvents.CONF`。
3. **Given** 二维码已过期，**When** 轮询得到 code 86038，**Then** 返回 `QrCodeLoginEvents.TIMEOUT`。
4. **Given** 使用 TV 通道二维码登录且轮询成功，**When** 构造凭据，**Then** 仍从结构化 cookie_info 字段正常取得全部字段，行为与现状一致。

---

### Edge Cases

- 响应标头中缺少任一构造凭据所必需的 Cookie（如无 bili_jct）时如何处理？——必须明确报错（见 User Story 2），不得回退为空值。
- 响应体中的 url 为不含 Cookie 查询参数的 crossDomain 跳转链接时如何处理？——不得再对该 url 的查询串做任何 Cookie 解析尝试（该格式已成为服务端现状）。
- 多个 Set-Cookie 标头共存、Cookie 名大小写差异（如 `DedeUserID`）时如何处理？——提取时须不区分大小写地匹配字段名。
- Cookie 值中含 URL 编码或特殊字符（如 `=`、`%`）时如何处理？——须原样保留字段值，不做会改变语义的二次解码。
- 同一 qrcode_key 在成功后再次轮询（重复确认）时如何处理？——幂等，凭据不被清空或改写为无效值。
- ac_time_value（refresh_token）在响应体中存在但 Cookie 齐全、或反之（Cookie 齐全但 refresh_token 缺失）时如何处理？——按必需字段缺失处理，报错并指明缺失项。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 网页端二维码登录在服务端判定成功后，系统 MUST 依据服务端本次随轮询响应实际下发的 Cookie 数据（Set-Cookie 标头，共 5 项，含 SESSDATA、bili_jct、DedeUserID）构造登录凭据，凭据中 SESSDATA、bili_jct、DedeUserID、ac_time_value 四个字段均不得为空。
- **FR-002**: 凭据构造 MUST NOT 依赖从响应体 url 字段查询串中解析 Cookie 的方式——该 url 已为不含 Cookie 的 crossDomain 跳转链接，此路径必须移除或替换，不得保留为可达代码。
- **FR-003**: refresh_token（对应凭据字段 ac_time_value）MUST 继续从轮询响应体中提取并写入凭据。
- **FR-004**: 当构造有效凭据所必需的任一字段缺失时，系统 MUST 抛出项目异常体系中的参数类异常并中止本次登录流程，MUST NOT 构造字段为空的部分凭据，MUST NOT 将登录状态判为 DONE。
- **FR-005**: Cookie 字段名匹配 MUST 不区分大小写（服务端下发形式为 `DedeUserID` 等原始大小写）。
- **FR-006**: 未扫码（86101→SCAN）、已扫码未确认（86090→CONF）、过期（86038→TIMEOUT）的状态判定行为 MUST 与现状一致。
- **FR-007**: TV 通道二维码登录的凭据构造路径 MUST 不受本次修改影响，仍使用其结构化 cookie_info 数据。
- **FR-008**: 异常消息与日志 MUST NOT 输出任何 Cookie 或令牌字段的值，只允许出现字段名与状态描述。

### Key Entities

- **登录凭据（Credential）**: 封装登录态的实体，关键属性为 SESSDATA、bili_jct、DedeUserID、ac_time_value（refresh_token），辅助属性为 buvid3、buvid4。本次特性保证前四项在网页端扫码登录成功后完整非空。
- **登录 Cookie 下发数据**: 服务端在轮询成功时随响应标头下发的一组 Cookie（实测共 5 项），是凭据构造的数据来源。其与凭据字段的对应关系为：SESSDATA→sessdata、bili_jct→bili_jct、DedeUserID→dedeuserid。
- **二维码登录会话（QrCodeLogin）**: 由 qrcode_key 标识的登录流程实体，维护轮询状态机（SCAN / CONF / TIMEOUT / DONE）与登录成功后的凭据。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 真机扫码确认登录的端到端用例中，100% 获得四项关键字段（SESSDATA、bili_jct、DedeUserID、ac_time_value）全部非空的凭据，不再出现"状态 DONE 但凭据为空"。
- **SC-002**: 使用该凭据调用任一需要登录态的只读接口，登录身份被成功识别。
- **SC-003**: 全量离线测试通过，既有测试套件无新增失败（状态判定与 TV 通道零回归）。
- **SC-004**: 必需字段缺失的场景在离线单元测试中被覆盖，且均在凭据构造环节以明确异常终止（单次轮询内暴露，错误信息可定位缺失字段）。

## Assumptions

- 服务端在轮询成功时通过响应 Set-Cookie 标头下发 5 个登录 Cookie，其中包含构造凭据所必需的 SESSDATA、bili_jct、DedeUserID（2026-09 实测；B 站接口可能随时再变，届时按"接口变更跟进上游"处理）。
- buvid3 / buvid4 不要求来自本次登录响应，允许沿用库内现有的自动生成机制补齐。
- 底层请求链路当前仅向上返回解析后的响应体；能否以及如何把服务端随响应下发的 Cookie 暴露给登录逻辑，属于实现决策，在计划阶段确定，不构成本规格的约束。
- 修复范围仅限网页端（WEB）通道；TV 通道凭据来源（结构化 cookie_info 字段）工作正常，不纳入本次改动。
- Cookie 提取与缺字段报错逻辑可通过离线单元测试用模拟响应验证；端到端验收需要真机扫码（复用 `scripts/qrcode_login.py` 验证脚本与 `pytest --login qrcode` 临时登录路径）。
