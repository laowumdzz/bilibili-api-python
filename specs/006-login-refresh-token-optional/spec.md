# Feature Specification: 扫码登录不再强制 ac_time_value（refresh_token）非空

**Feature Branch**: `006-login-refresh-token-optional`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "修改 scripts/login_and_cache.py 登录逻辑,不判断 ac_time_value(refresh_token) 的值是否为空(大部分情况下无影响,ac_time_value只用来刷新cookie)"

**背景**: `scripts/login_and_cache.py` 的扫码登录流程底层调用 WEB 通道二维码登录（`bilibili_api/login_v2.py`）。该通道在服务端判定登录成功后，要求 SESSDATA、bili_jct、DedeUserID、ac_time_value 四个字段全部非空，任一为空即抛参数类异常并中止整个登录。现实中 B 站可能不随轮询响应下发 refresh_token（或下发为空值），此时登录 Cookie 已齐全、登录态实际可用，却被该判断整体判败，导致临时登录失败、凭据无法写入缓存。ac_time_value 在本项目中的唯一用途是凭据过期后的刷新（`scripts/login_and_cache.py` 的 `check_cache` 刷新路径），其值为空不影响任何其他需登录态的调用。

**与 specs/002 的关系**: 本特性显式修订 specs/002-qrcode-login-cookie-fix 中 FR-001 / FR-004 关于"ac_time_value 属登录必需字段、缺失须报错中止"的约定（该校验曾于 2026-09-12 恢复，本次仅对 ac_time_value 废除）。SESSDATA / bili_jct / DedeUserID 三个 Cookie 字段的必需性与既有报错行为保持不变。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - refresh_token 缺失时扫码登录仍成功 (Priority: P1)

库使用者（含 `scripts/login_and_cache.py` 临时登录流程）通过 WEB 通道二维码登录：扫码并在手机确认后，即使服务端未随轮询响应下发 refresh_token（或其值为空），登录也应判定成功，得到的凭据中三个 Cookie 字段（SESSDATA、bili_jct、DedeUserID）完整可用，仅 ac_time_value 为空。凭据可正常调用需登录态的接口；临时登录流程成功并把非空字段写入 TEMP 缓存文件。

**Why this priority**: 这是本特性的全部价值所在。当前缺陷使"B 站未下发 refresh_token"场景下的扫码登录 100% 失败——Cookie 明明已下发却因一个仅用于刷新的可选字段被整体判废，登录流程完全不可用。

**Independent Test**: 以构造的模拟响应（Cookie 齐全、响应体无 refresh_token 或为空串）驱动 WEB 通道扫码轮询（离线单元测试，无需真机），断言状态判定为 DONE、凭据可取得、三个 Cookie 字段非空且 ac_time_value 为空；再由真机扫码验收正常下发场景无回归。

**Acceptance Scenarios**:

1. **Given** WEB 通道轮询响应判定登录成功且 Cookie 齐全，**When** 响应体缺少 refresh_token 字段，**Then** 登录判定为 DONE，不抛任何异常。
2. **Given** 同上场景但响应体 refresh_token 为空字符串，**When** 构造凭据，**Then** 凭据构造成功，SESSDATA、bili_jct、DedeUserID 保持响应下发的值，ac_time_value 为空（None 或空串）。
3. **Given** ac_time_value 为空的登录凭据，**When** 调用任一需登录态的只读接口，**Then** 服务端将其识别为已登录用户。
4. **Given** `scripts/login_and_cache.py` 以扫码方式完成上述登录，**When** 登录成功，**Then** 缓存文件写入全部非空字段（不含 ac_time_value 或其值为空时不写入该键），脚本退出码为 0。

---

### User Story 2 - 空 ac_time_value 凭据的缓存链路行为不变 (Priority: P2)

ac_time_value 为空的凭据进入 TEMP 缓存链路后，一切既有语义保持不变：缓存文件合法性判定中 ac_time_value 本就是可选字段；联网校验通过则直接使用；凭据过期时因缺少刷新材料按"过期且无刷新材料"终态处理（删除缓存文件并按回退链回退），不得因本特性改变。

**Why this priority**: 本特性放宽登录门槛后，"无 ac_time_value 的缓存凭据"从边缘态变为常见态，缓存校验 / 刷新 / 回退链路必须被显式证明仍然正确，防止放宽引入静默劣化。

**Independent Test**: 离线单元测试覆盖三态：不含 ac_time_value 键的缓存文件合法性判定通过；凭据校验通过路径直接复用；凭据过期且无 ac_time_value 时缓存文件被删除并返回"过期且无刷新材料"终态。

**Acceptance Scenarios**:

1. **Given** 缓存文件不含 ac_time_value 键但其余必需字段齐全，**When** 读取并判定缓存合法性，**Then** 判定为合法可用。
2. **Given** 无 ac_time_value 的缓存凭据，**When** 联网有效性校验通过，**Then** 凭据直接投入使用，不尝试刷新。
3. **Given** 无 ac_time_value 的缓存凭据已过期，**When** 联网校验失败，**Then** 缓存文件被删除、返回"过期且无刷新材料"终态，需登录用例按回退链处理（pytest 侧警告并跳过）。

---

### User Story 3 - 必需字段校验与其余登录通道无回归 (Priority: P3)

放宽仅针对 ac_time_value：SESSDATA、bili_jct、DedeUserID 任一缺失或为空时仍须明确报错（异常消息含字段名、不含凭据值）；TV 通道扫码、短信验证码登录、扫码未确认 / 过期等状态判定行为均与现状一致。

**Why this priority**: 修改发生在登录成功判定的同一代码路径上，必需字段的保护与其余通道的邻接逻辑必须被显式回归锁定，防止放宽范围意外扩大。

**Independent Test**: 离线单元测试分别模拟缺任一必需 Cookie、Cookie 值为空串的响应，断言仍抛参数类异常且消息语义不变；TV 通道与三种轮询状态（SCAN / CONF / TIMEOUT）用例沿用现状断言。

**Acceptance Scenarios**:

1. **Given** WEB 通道登录成功响应缺少 SESSDATA / bili_jct / DedeUserID 任一项（或值为空串），**When** 轮询判定成功并构造凭据，**Then** 抛参数类异常，消息指明缺失字段名且不含任何凭据值，登录不被标记为完成。
2. **Given** TV 通道扫码登录成功，**When** 构造凭据，**Then** 仍从结构化 cookie_info 取得全部字段（含 refresh_token），行为与现状一致。
3. **Given** 未扫码（86101）/ 已扫码未确认（86090）/ 二维码过期（86038），**When** 轮询，**Then** 状态判定与现状一致，全程不构造凭据。
4. **Given** 短信验证码登录成功（含风控二次验证分支），**When** 构造凭据，**Then** 行为与现状一致（该路径本就不对 ac_time_value 做非空阻断）。

---

### Edge Cases

- 响应体 refresh_token 字段完全缺失与取值为空字符串两种形态如何处理？——统一按"空"处理，登录成功、ac_time_value 为空，不区分报错。
- refresh_token 下发为非字符串类型（如数字）时如何处理？——按现状的归一逻辑处理：仅真值为空时视为空；非空真值经字符串归一（`str()`）后写入凭据，不视作空。
- ac_time_value 为空的凭据后续显式发起刷新时如何处理？——维持既有失败语义（缺刷新材料无法刷新），本特性不赋予其新的刷新能力，也不因此报新的错误形态。
- 空 ac_time_value 写入 TEMP 缓存时如何处理？——沿用现有"仅写入非空字段"规则，缓存文件不出现值为空的 ac_time_value 键。
- 多次轮询同一 qrcode_key（登录成功后重复确认）时如何处理？——幂等，凭据不被清空或改写，ac_time_value 空值判定结果稳定。
- 二维码续期（连续超时上限内重新生成）后登录成功且无 refresh_token 时如何处理？——与首次生成一致，登录成功、ac_time_value 为空。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: WEB 通道二维码登录在服务端判定成功后，凭据构造的必需字段校验 MUST 仅覆盖 SESSDATA、bili_jct、DedeUserID 三项；ac_time_value MUST NOT 参与必需性判定，其值缺失或为空时不得抛出异常、不得阻断登录。
- **FR-002**: refresh_token 在响应体中存在且非空时，系统 MUST 仍将其提取写入凭据的 ac_time_value 字段，不得因本特性丢弃该值。
- **FR-003**: ac_time_value 为空时构造出的凭据 MUST 可正常取得并使用：三个 Cookie 字段保持响应下发值，登录状态判定为成功；空值表达形态（None 或空串）MUST 在缓存写入与刷新判定链路上行为等价（均为假值）。
- **FR-004**: SESSDATA、bili_jct、DedeUserID 任一缺失或为空串时，系统 MUST 维持现状：抛项目异常体系中的参数类异常、消息指明缺失字段名且不含凭据值、登录不标记为完成。
- **FR-005**: `scripts/login_and_cache.py` 的扫码登录流程 MUST 在 ac_time_value 为空时照常成功：缓存文件写入全部非空字段（ac_time_value 不写入或以缺省形态存在），脚本以成功码退出；中止 / 失败路径的消息语义不变。
- **FR-006**: TEMP 缓存链路（文件合法性判定、联网校验、过期刷新、无刷新材料删除、回退）MUST 保持既有语义；ac_time_value 缺失的缓存凭据有效时直接使用、过期时删除缓存文件并按"过期且无刷新材料"终态回退；重新登录成功覆写缓存时，旧缓存中的 ac_time_value MUST 随覆盖写一并清除，MUST NOT 残留形成“旧 refresh_token 搭配新 Cookie”的混合态。
- **FR-007**: TV 通道扫码登录、短信验证码登录（含风控二次验证）、密码登录的凭据构造与状态判定行为 MUST 与现状一致，不得因本特性改变。
- **FR-008**: 既有断言"WEB 通道缺 refresh_token 须报错"的离线用例 MUST 更新为断言新行为（登录成功 + ac_time_value 为空）；断言必需 Cookie 缺失报错、TV 通道、状态判定、缓存链路的既有用例 MUST 保持通过。

### Key Entities

- **登录凭据（Credential）**: 封装登录态的字段集合。本特性后其字段分为两层语义——登录必需字段（SESSDATA、bili_jct、DedeUserID，缺失即登录失败）与可选字段（ac_time_value 仅服务于凭据刷新、buvid3 / buvid4 服务于设备标识），可选字段为空不影响凭据可用性。
- **TEMP 登录缓存文件**: 交互式登录成功后写入的凭据缓存，仅含非空字段；ac_time_value 在其中为可选键，其缺失不触发非法判定，仅在"凭据过期需刷新"时决定是否存在刷新材料。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 以模拟响应驱动 WEB 通道扫码登录（Cookie 齐全、refresh_token 缺失或为空）时，登录成功率 100%（判定成功且凭据可取得），而修改前同场景成功率 0%（必抛参数异常）。
- **SC-002**: 模拟场景回归全绿：缺任一必需 Cookie 仍报错、TV 通道与短信登录凭据构造不变、三种轮询状态判定不变、缓存链路三态（合法 / 直接使用 / 过期删除回退）不变。
- **SC-003**: 真机扫码登录（refresh_token 正常下发场景）端到端无回归：登录成功、凭据身份被服务端识别、缓存文件字段齐全。
- **SC-004**: 项目质量门禁（lint 脚本全链路）与全量离线测试通过。

## Assumptions

- B 站近期在部分 WEB 扫码登录轮询响应中不下发 refresh_token 或下发空值，是触发本需求的现实背景（用户观察）；本特性按"该字段可选"的长期语义适配，不针对特定接口版本做探测或兼容分支。
- ac_time_value 仅用于凭据过期刷新，不参与 Wbi 签名、buvid / bili_ticket 获取等反爬链路，也不被任何需登录态的业务接口校验——若未来出现依赖该字段的接口，属于独立的新问题。
- 空 ac_time_value 的具体表达形态（None 或空字符串）由实现阶段决定，但须满足 FR-003 的等价性约束。
- `scripts/login_and_cache.py` 自身不含 ac_time_value 非空判断（其判断点位于上游 WEB 通道登录实现中），本特性对脚本侧的要求仅为流程级验收（FR-005），不预设脚本代码必须改动。
- 凭据校验（check_valid）不依赖 ac_time_value，空值不影响有效性判定结果。
