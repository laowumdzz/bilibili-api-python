# Feature Specification: 清零 pyrefly 存量类型错误（1064 条）

**Feature Branch**: `005-pyrefly-type-debt`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "修复pyrefly剩余的1064 条存量"

## User Scenarios & Testing *(mandatory)*

**背景（现状实测，2026-09-25）**：类型检查器默认门禁当前全绿，但这是靠
9 个错误码的豁免表换来的——豁免类别下的存量错误共 1061 条被静默压制，
另有 3 条残留码错误，合计 1064 条"隐性类型债"，分布于 `bilibili_api/`
下 60 个源文件。按错误码分布：bad-return 387、bad-index 280、
unsupported-operation 184、bad-argument-type 68、bad-assignment 57、
missing-attribute 35、bad-override 20、bad-function-definition 17、
not-iterable 13、bad-override-mutable-attribute 2、bad-override-param-name 1。
按文件前列：login_v2.py 73、_live_danmaku.py 67、user.py 65、live.py 64、
bangumi.py 64、video.py 60、video_uploader.py 53、dynamic.py 41。

本项目宪法（Core Principles III 质量门禁）已规定：豁免错误码基线只减不增，
某错误码清零后必须从豁免表移除、恢复默认拦截。本特性即把这一承诺推进到终点。

### User Story 1 - 贡献者的类型门禁恢复全额拦截 (Priority: P1)

作为项目贡献者，我希望 9 个被豁免的错误码全部恢复默认启用，这样我新写的
代码里任何类型错误（不只是未豁免类别）都会在提交前被 CI 门禁直接指出位置，
而不是混入豁免类别的存量里、只能靠"只减不增"棘轮间接兜底。

**Why this priority**: 门禁拦截力是本项目宪法规定的不可协商红线；豁免每多
存在一天，豁免类别内的新增类型错误就多一天只能靠计数对比被发现，定位差、
易漏拦。这是本特性的核心价值。

**Independent Test**: 任选一个错误码（如 not-iterable，13 条）先行清零并从
豁免表移除；在任意文件故意引入一个该类错误，`uv run python scripts/lint.py`
必须非零退出并精确报出文件行号。即使其余错误码尚未修复，这一条也独立成立、
独立交付。

**Acceptance Scenarios**:

1. **Given** 全部豁免条目已移除，**When** 贡献者引入一条 bad-return 类型
   错误并运行门禁，**Then** 门禁非零退出，错误信息含文件、行号与错误码
2. **Given** 某错误码存量已清零但豁免条目仍残留，**When** 维护者复查，
   **Then** 该状态被视为不合格——清零与移除必须成对完成（宪法 III）

---

### User Story 2 - 维护者按批次推进棘轮直至清零 (Priority: P1)

作为维护者，我希望把 1064 条存量按错误码（辅以按模块）分批修复：每修完
一批就下调棘轮基线，修完一个错误码就移除一条豁免。任何中间批次合入后，
仓库都处于"门禁绿 + 棘轮基线低于上一批"的合法状态，直到 9 条豁免全部
退役、基线清空。

**Why this priority**: 棘轮机制保证每批工作独立可合入、可回滚，不需要
"一次性大爆炸修复"这种高风险交付；这也是宪法规定的存量处置方式。

**Independent Test**: 每批次结束后运行 `uv run python scripts/type_ratchet.py`：
所有错误码实际计数 ≤ 基线，且较上一批严格下降（或持平但另一码下降）；
`uv run python scripts/lint.py` 全绿。

**Acceptance Scenarios**:

1. **Given** bad-argument-type 实际存量 68 而冻结基线 69（历史差 1 条），
   **When** 本特性启动，**Then** 第一动作是无代码变更地把基线下调到实测值，
   先校准再修复
2. **Given** 某批修复了 not-iterable 全部 13 条，**When** 维护者提交，
   **Then** 棘轮基线中该码归零删除、pyproject 豁免表移除该条目、门禁全绿，
   三者出现在同一批次的交付里
3. **Given** 修复期间某错误码计数意外回升，**When** 运行棘轮脚本，
   **Then** 脚本非零退出阻断，直到回升被查明并消除

---

### User Story 3 - 下游使用者获得更准的类型提示且行为零变化 (Priority: P2)

作为库的下游使用者（IDE 用户 / 依赖本库做静态检查的项目），我希望公共
API 的类型注解变得准确可信（补全更准、我项目里的类型检查器少报误判），
同时所有公共函数的运行时行为与签名完全不变——这是一次纯类型层面的修复，
不应让我升级时遇到任何破坏。

**Why this priority**: 类型债的直接受害者是下游的开发体验；但行为兼容是
库的接口契约（宪法 V），一旦破坏代价大于收益，故列 P2 并以"零破坏"为
硬约束。

**Independent Test**: 每批次后 `uv run pytest -m "not integration"` 全绿；
全部完成后人工核对公共模块导出符号的签名兼容（或以类型层面的对外快照
对比确认无收窄、无删参）。

**Acceptance Scenarios**:

1. **Given** 某公共函数原先返回注解含混（是 bad-return 存量来源），
   **When** 修复完成，**Then** 注解反映真实返回结构，且函数运行时行为
   （返回值、异常、副作用）与修复前一致
2. **Given** 修复过程中发现某条类型错误背后是真实逻辑 bug，**When**
   需要改行为才能修，**Then** 行为修复拆分为独立提交并单独评估兼容性，
   不与类型修复混在同一提交（宪法 V：一事一提交）

---

### User Story 4 - 维护者收编残留码并让豁免机制退役 (Priority: P3)

作为维护者，我希望顺带修复 3 条残留码错误（bad-override-mutable-attribute
×2、bad-override-param-name ×1），把它们从棘轮脚本的 KNOWN_RESIDUAL
例外集合与相关注释中清理掉；全部存量清零后，pyproject 与脚本的注释更新
为反映"豁免已退役"的现状，避免文档性注释继续描述已不存在的东西。

**Why this priority**: 数量小、价值在整洁与一致性，属于收尾性质，但若不
做会留下"注释说还有残留、实际已无"的漂移，违反本项目文档单一事实源原则。

**Independent Test**: 强制全码检查（棘轮同口径命令）输出 0 条错误；
`grep` 确认 KNOWN_RESIDUAL 与豁免表注释不再描述未修状态。

**Acceptance Scenarios**:

1. **Given** 3 条残留码已修复，**When** 运行棘轮同口径强制检查，
   **Then** 输出不含任何 bad-override-mutable-attribute 或
   bad-override-param-name
2. **Given** 全部 1064 条清零，**When** 阅读 pyproject.toml 与
   type_ratchet.py，**Then** 注释准确描述当前机制（豁免表空、基线空），
   无过时描述

---

### Edge Cases

- **pyrefly 升级导致误报口径变化**：修复期间 pyrefly 大版本升级可能让
  同一批代码的错误数漂移（历史上出现过 3.10 泛型误报，v18.0.0 用 cast
  归一处理）。默认锁定现有 pyrefly 版本口径；确需升级时先重测全量计数、
  在提交说明中记录口径变化，再继续修复。
- **确认的 pyrefly 误报**：允许以 cast（或带理由注释的局部忽略）处理，
  但每一处必须注释说明误报依据；禁止把 cast/Any 当作通用消音器批量使用。
- **类型错误背后的真实 bug**：修复中若发现逻辑错误（类型注解与实际行为
  不符是因为行为错了），行为修复独立提交；涉及公共接口破坏时优先寻找
  兼容修法，实在无法避免才用 BREAKING CHANGE footer 标注（目标为零）。
- **一条语句多个错误**：min-text 输出以行为单位，一行可能叠加多条错误；
  批次计数以棘轮同口径命令输出为准，避免"修了一条计数没降"引发误判。
- **修复引发连锁**：收紧某处注解可能让下游调用点暴露新错误（错误从一码
  转移到另一码）。验收以"总计数下降且无回升码"为准，而非单码孤立看待。
- **基线既有差值**：bad-argument-type 实测 68 < 基线 69，启动时先下调，
  保证后续一切对比基于真实值。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 本特性 MUST 以 2026-09-25 实测的 1064 条为总目标口径
  （9 个豁免码 1061 条 + 3 条残留码），全部修复至强制全码检查输出 0 条。
- **FR-002**: 修复 MUST 分批进行：以错误码为主线（小码优先清零退役、
  大码拆批），辅以按模块聚合；每个批次独立通过全量门禁并可独立合入。
- **FR-003**: 某错误码存量清零后，MUST 在同一批次内完成三件事：棘轮基线
  删除该码、pyproject 豁免表移除该条目、门禁复跑全绿（宪法 III 强制）。
- **FR-004**: 修复手段 MUST 以精确类型注解、类型收窄、修正错误注解为主；
  cast 与局部忽略 ONLY 允许用于经确认的工具误报，且每处附误报依据注释；
  MUST NOT 以 Any / 大面积 cast 消音压计数。
- **FR-005**: 公共 API MUST 保持向后兼容：不删除公开参数、不收窄公开
  签名、不改变默认行为；发现必须改行为的真实 bug 时，行为修复 MUST 拆分
  为独立提交并单独评估，无法避免的破坏性变更 MUST 按 Conventional Commits
  规则以 BREAKING CHANGE footer 标注（本特性目标为零破坏）。
- **FR-006**: 每个批次合入前 MUST 通过 `uv run python scripts/lint.py`
  全量门禁与 `uv run pytest -m "not integration"` 离线测试（本条为
  FR-002"独立通过全量门禁"的命令化验收口径，二者分工不重复）。
- **FR-007**: 涉及公共符号的注解或 docstring 变更后，MUST 重新运行
  `uv run python scripts/doc_gen.py` 生成文档，确保 `docs/modules/` 无漂移
  （宪法 III：文档由源码生成）。
- **FR-008**: 3 条残留码（bad-override-mutable-attribute、
  bad-override-param-name）MUST 一并修复，并从棘轮脚本的例外集合与
  pyproject 相关注释中清理，注释 MUST 与清零后现状一致。
- **FR-009**: 提交粒度 MUST 遵循"一个提交只做一件事"：类型修复、基线
  下调、行为修复各自独立提交；提交信息遵循 Conventional Commits。
- **FR-010**: 全部完成后 MUST 达到终态：强制全码检查 0 条错误、
  `[tool.pyrefly.errors]` 豁免表为空、棘轮基线为空且脚本仍正常运行通过。

### Key Entities *(include if feature involves data)*

- **类型错误存量（Type Error Inventory）**: 被豁免压制的 1064 条错误，
  属性为错误码、所在文件、行号；本特性的清零对象，随批次单调递减。
- **豁免表（Exemption Table）**: pyproject 中将 9 个错误码设为不拦截的
  配置；随对应错误码清零逐条退役，终态为空。
- **棘轮基线（Ratchet Baseline）**: 存量计数脚本中冻结的各错误码上限，
  只减不增；是批次验收与回归拦截的度量衡。
- **批次（Remediation Batch）**: 一组同错误码（或同模块）修复 + 对应
  基线下调 + 门禁验证的组合交付单元，独立可合入。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 以棘轮同口径强制检查测量，类型错误存量从 1064 条降至
  0 条（可分批达成，每批严格下降）。
- **SC-002**: `[tool.pyrefly.errors]` 豁免条目数从 9 降至 0；棘轮脚本
  基线条目数从 9 降至 0，且脚本在空基线状态下正常运行并通过。
- **SC-003**: 终态运行 `uv run python scripts/lint.py` 全绿；任意引入
  一条曾豁免类别的错误（如 bad-return）时门禁非零退出并报出精确位置。
- **SC-004**: 全部离线测试通过率 100%，且全程公共 API 破坏性变更数为 0。
- **SC-005**: `docs/modules/` 与源码零漂移（门禁文档漂移校验通过）。
- **SC-006**: 交付全程豁免基线无任何一次上调，每个中间批次合入时门禁
  均为绿色（不存在"先合一半红的、最后补绿"的中间态）。

## Assumptions

- 存量口径以 2026-09-25 实测为准（9 豁免码 1061 + 残留 3 = 1064）；
  启动时先把 bad-argument-type 基线从 69 校准下调到实测 68。
- 修复期间保持现有 pyrefly 版本与测量命令口径不变；如必须升级，先重测
  全量计数并在提交说明记录口径变化后继续。
- 范围仅覆盖 `bilibili_api/` 库源码（1064 条全部位于其中）；`tests/`、
  `scripts/`、`docs/` 不在类型检查范围内，不产生存量。
- 分批交付允许多个提交乃至多个 PR 完成；本特性生命周期跨越全部批次，
  终态以 FR-010 为准。
- 修复以静态正确性为目标，不追求借机重构；顺带发现的真实 bug 按拆分
  原则另行处置。
- 工作分支遵循用户现行实践（本地 main 维护性直提交），如需 PR 则目标
  分支为 dev。
