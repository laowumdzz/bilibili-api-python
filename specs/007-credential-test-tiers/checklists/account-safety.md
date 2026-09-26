# 账号安全与风控边界需求质量检查单：集成测试按重要程度分级重构

**Purpose**: 检验特性 007 全部需求制品（spec / plan / research / data-model / contracts / quickstart）中"账号安全与风控边界"相关需求的编写质量——完备、清晰、一致、可测，而非验证实现行为
**Created**: 2026-09-26
**Feature**: [spec.md](../spec.md)

**Note**: 本检查单由 `$speckit-checklist` 命令基于特性上下文生成。
**Review Ownership**: 本检查单是评审者持有的需求质量评审工件。仅当评审者判定该需求质量标准满足时才勾选 `[x]`。
**Marker Semantics**: `[x]` 表示该标准已评审且需求质量满足；不表示实现工作完成。

## 需求完备性（安全判据与类别覆盖）

- [x] CHK001 - 五类操作判定表（可逆写 / 自身状态类 / 资源消耗类 / 公开发布类 / 破坏性·身份特定类）是否对"新增用例无法对号入座"的残余情形定义了兜底归层规则（默认从严入 cred3 还是报错待裁）？[Gap, data-model §账号安全策略]
- [x] CHK002 - "自身状态类"白名单的准入三条件（仅自身可见、不属于六态清单、无对外发布形态）之外，是否定义了白名单操作的**追加与移除流程**（谁判定、依据什么、成文到哪）？[Completeness, data-model §账号安全策略]
	- **不建流程，补两条规则——“封闭枚举 + 证据义务 + 从严回退”**
- [x] CHK003 - 需求是否覆盖了六态清单之外其他残留敏感状态的归层处置——观看历史上报（report_watch_history 写入历史记录）、直播签到（每日一次不可逆）已被列入 cred2 白名单，其残留判定依据是否在需求中成文？[Coverage, data-model §账号安全策略 / spec FR-006]
- [x] CHK004 - 现有全部 38 个集成文件是否都能在权威映射表中找到唯一归层（含被合并、被更名、被除名的用例的去向说明）？映射表是否声明了"新增用例必须先入表"的维护义务？[Completeness, data-model §权威分层映射表]
- [x] CHK005 - cred3 内部是否需要二级风险区分（真金消费 vs 破坏性 vs 身份特定）——将来牺牲账号环境下"允许跑破坏性但禁真金"之类的选择性需求是否被预见或显式排除？[Gap, spec FR-003]

## 需求清晰性（判据可判定、术语量化）

- [x] CHK006 - FR-008 中"第三方高流量内容"的"高流量"是否有可判定定义，还是仅靠"自有内容"的正向判据兜住全部情形（即：非自有 = 禁止，无需流量判定）？若为后者，需求是否已把判据收敛为正向表述以消除歧义？[Clarity, spec FR-008]
- [x] CHK007 - "自有内容"的判定标准是否唯一——data-model 规定运行时 `get_self_info` → `get_videos` 动态解析，若账号有自有视频但含"仅可见自己"的私密稿件，是否仍算合格评论目标？[Ambiguity, research R5 / data-model §校验规则]
- [x] CHK008 - 请求预算中的"一次对外请求"计数口径是否定义精确（HTTP 重试是否计数、反爬参数预取（buvid/ticket/wbi）是否计数、WebSocket 连接与心跳是否计入 ≤30 / ≤400）？[Clarity, contracts §6 / spec FR-004]
	- **采用“服务端视角全计数”——对 B 站域名实际发送的每次 HTTP 请求计 1，其余全部不计入或单列**
- [x] CHK009 - "全程零 412"的判定口径是否定义（仅统计响应码 412，还是含等效风控错误码 / -352；限速间歇后的偶发 412 是否计入）？[Measurability, spec SC-002]
	- "全程零 412"不定义,仅统计,含等效风控错误码,偶发也计入
- [x] CHK010 - FR-010"循环内节流"的具体值在 spec 层未钉（research R8 定 0.5s）——规格与设计文档间的数值锚定关系是否成文（spec 定原则、research 定值的分层是否明确）？[Clarity, spec FR-010 / research R8]

## 需求一致性（跨制品对齐）

- [x] CHK011 - spec FR-007（创作中心、私信发送、房管操作 MUST 归 cred3）与 data-model 映射表、research R6/R7 的归层结论是否逐项一致，无任一用例在两处归层不同？[Consistency, spec FR-007 / data-model §cred3]
- [x] CHK012 - spec 的六态清单（关注 / 收藏 / 点赞 / 评论 / 弹幕 / 稍后再看）与 data-model、quickstart V3 的六态核对表是否逐字一致？[Consistency, spec FR-006 / quickstart V3]
- [x] CHK013 - spec FR-010 要求"**凭据用例之间**启用非零默认间隔"，而实现语义（conftest ratelimit fixture）是对全部 integration 用例（含匿名）间隔——需求与实现语义的差异是否被需求文档显式认可或收敛（匿名用例是否也应间隔）？[Consistency, spec FR-010 / contracts §5]
- [x] CHK014 - spec Assumptions 允许实现阶段改写分层标记名（cred0–cred3 为约定名），与 contracts / data-model / quickstart 已按 cred0–cred3 写死的命令矩阵、映射表之间的追溯关系是否成文（改名时哪些文档须同步）？[Traceability, spec Assumptions / contracts §2]
- [x] CHK015 - `pytest -m integration`（contracts §7 声明"现在剔除 cred3"）与 spec FR-003"默认全量运行 = cred0–cred2"两种表述覆盖的运行形态是否一致无死角（无 `-m` 默认、`-m integration`、`-m "not integration"` 三态各自范围是否都有明确定义）？[Consistency, spec FR-003 / contracts §2 §7]

## 验收标准可测性

- [x] CHK016 - SC-003 六态零残留的核验方法是否定义为可操作口径（基线何时采集、六态各自以什么接口 / 字段比对、由人工还是命令输出比对）？[Measurability, spec SC-003 / quickstart V3]
- [x] CHK017 - SC-001 的"除缺凭据外无跳过"与 cred2 条件跳过（无自有视频时）的边界是否互斥清晰——各 SC 条款约束的层范围是否逐条标注，避免验收时张冠李戴？[Clarity, spec SC-001 / research R5]
- [x] CHK018 - SC-002 / SC-007 的验收是否显式钉定在默认限速（1.5s）与单账号环境下运行——若执行者以 `BILI_RATELIMIT=0` 或多账号环境跑出全绿，验收口径是否排除该结果？[Measurability, spec SC-002 / research R3]
	- 按照默认限速以及单账号运行
- [x] CHK019 - SC-004"收集即排除"的核验命令口径（`--collect-only` 计数为 0 + 显式点名可收集）是否与"执行数为 0"的表述统一为同一验收动作，二者是否会给出分歧结论（如 skipif 遗留导致的收集非零执行为零）？[Measurability, spec SC-004 / contracts §3]
- [x] CHK020 - 请求计数器（BILI_COUNT_REQUESTS）的输出是否被定义为验收的唯一权威读数，quickstart V1/V2 是否声明"以该读数判定预算达标"从而排除人工估算？[Measurability, contracts §6 / quickstart V1 V2]

## 场景与边界覆盖（失败 / 降级 / 中止路径）

- [x] CHK021 - 生命周期用例**中途失败**的残留处置是否被需求覆盖——单用例内"评论已发、点赞步骤失败"时，用例中止后的清理义务（teardown 级恢复还是仅首尾配对）是否定义？[Gap, Edge Case, spec FR-006 / research R4]
	- **无论用例成功、失败、超时、中断，均执行 teardown 清理**
- [x] CHK022 - 清理步骤失败的"有限重试次数"是否量化，重试后仍失败的残留警告是否要求列出具体残留物（哪条评论 / 哪个收藏夹）以便人工恢复？[Clarity, spec Edge Cases / FR-006]
- [x] CHK023 - 凭据在运行中途过期的处置需求（沿用现状失败语义）是否与 SC-002"100% 通过"的验收冲突——验收运行若遇凭据中途失效，重跑策略是否定义？[Ambiguity, spec Edge Cases / SC-002]
- [x] CHK024 - 412 风控在验收运行中**实际发生**时的应对需求是否定义（立即中止防加重、退避多久可重试、还是仅记为验收失败）？[Gap, Exception Flow, spec FR-005 / SC-002]
	- 立即中止防加重
- [x] CHK025 - 条件跳过（无自有视频 / 上游死接口容忍）的统计口径是否会影响 SC-001 / SC-002 的"通过率 100%"判定——跳过与容忍通过在验收读数中是否被区分呈现？[Measurability, spec FR-012 / SC-001 SC-002]

## 依赖与假设有效性

- [x] CHK026 - "共享账号持 2 个自有视频"这一关键假设（2026-09-26 实测）失效时（删稿 / 换号）的影响范围与回退行为（cred2 条件跳过、SC-003 部分验收降级）是否成文为可检测的假设而非隐式依赖？[Assumption, research R5 / data-model §校验规则]
- [x] CHK027 - `BILI_RATELIMIT` 缺省值 0→1.5 的行为变更对既有使用者的通告义务（AGENTS.md / CHANGELOG / conftest docstring 之外是否还需 CI 配置同步说明）是否在需求中列全？[Dependency, spec FR-010 / plan §V]
- [x] CHK028 - 本特性"不新增功能模块集成覆盖"的范围排除（login_v2 / video_uploader 缺口仅记录）是否有明确的去向（issue / 待办清单），避免范围外缺口被遗忘？[Dependency, spec Assumptions]
	- 暂无任何issue/待办清单

## Notes

- 勾选权在评审者：仅当评审确认对应需求质量标准满足时标记 `[x]`；仍需澄清、修正或评审评估的条目保持 `[ ]`
- `$speckit-implement` 读取本检查单勾选状态作为门禁，但不得修改勾选标记
- `checklists/requirements.md` 是 `$speckit-specify` / `$speckit-clarify` 维护的独立内置规格质量清单，与本单生命周期不同
- 发现需求缺陷时建议就地附注（条目下方加缩进注释），并回写 spec / data-model / contracts 后再复评
- 编号连续（CHK001–CHK028），便于评审引用
