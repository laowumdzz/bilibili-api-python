# Research: 集成测试按重要程度分级重构（特性 007）

**Date**: 2026-09-26
**Status**: Phase 0 完成，全部未知项已解决（无 NEEDS CLARIFICATION 遗留）

## 研究输入

- 特性规格：`specs/007-credential-test-tiers/spec.md`
- 全量测试盘点（2026-09-26，38 个集成文件 / 313 用例 / 约 200 个需凭据）已完成并作为分层映射底稿
- 库内清理配对 API 实地核查（见 R6 / R7）
- 共享测试账号只读探测（2026-09-26 实测）：mid=479269916，等级 5，VIP 有效，**拥有 2 个自有视频**（aid 114603837097572、114443430137404）

---

## R1: 分级标记机制与层级选择器实现方式

**Decision**: 采用四个 pytest marker（`cred0` / `cred1` / `cred2` / `cred3`，经 `pytest.ini_options` 注册）+ `conftest.py` 的 `pytest_collection_modifyitems` 收集期排除实现：

- `-m cred0`、`-m "cred0 or cred1"`、`-m "cred0 or cred1 or cred2"` 直接使用 pytest 原生布尔表达式；
- 收集期规则：当 `-m` 表达式（`config.option.markexpr`）**不含** `cred3` token 时，收集阶段即剔除全部 `cred3` 用例（满足 SC-004"收集即排除"）；显式 `-m cred3` 或表达式含 `cred3` 时保留；
- 默认全量运行（不带 `-m`）= 离线 + 匿名集成 + cred0–cred2（cred3 收集即剔除）。

**Rationale**: marker 是 pytest 原生选择原语，累加范围选择零成本；收集期排除复用现有 `pytest_collection_modifyitems` 钩子（该钩子现已存在，负责打 integration 标记），改造点集中、diff 最小。

**Alternatives considered**:

1. 自定义 `--cred-levels` CLI 选项 —— 引入与 `-m` 并存的第二套选择器，心智负担与文档成本高，弃用；
2. cred3 用 `skipif` 环境变量门控 —— 跳过不等于收集排除，与 SC-004 验收口径冲突，弃用；
3. 按层拆分目录移动文件 —— 破坏 38 个文件的 git 历史与最小 diff 原则，弃用。

---

## R2: 漏标防护机制（FR-001 "未标注可发现"）

**Decision**: 运行时防护改为**收集期防护**为主 + 文件级标注约定（2026-09-26 按 analyze 发现 I1/U1 修订，弃用原"credential fixture 运行时检查"方案——`--collect-only` 不执行 fixture，运行时方案无法支撑 T051 终态门禁）：

- 分层标注优先落在**文件级** `pytestmark = [pytest.mark.credX]`（约 30 个文件整文件同层，天然简单）；
- 混合文件（video / user / live / dynamic / comment / favorite_list / rank / article / audio / topic / video_tag / manga / session）用例级标注；
- `pytest_collection_modifyitems` 中经 `item.fixturenames` 传递闭包识别需凭据用例（闭包含模块级 fixture 间接依赖），收集期检查——未携带任一 cred 标记、或携带多个 cred 标记（违反"恰好一层"）均 `warnings.warn`（终端可见）；`BILI_STRICT_TIERS=1` 时升级为收集错误中止会话（供门禁与严格模式使用，`--collect-only` 下同样生效）。

**Rationale**: "经模块级 fixture（如 `video` / `room`）间接依赖 credential"的传递闭包静态扫描难以可靠计算；fixture 运行时能拿到首个请求节点，检查廉价且准确。文件级标注让绝大多数场景退化为一条 `pytestmark`。

**Alternatives considered**: lint 脚本静态扫描 fixture 依赖图（闭包计算复杂、误报难消）；不做防护（违反 FR-001）。

---

## R3: 限速安全默认值与循环内节流（FR-010）

**Decision**:

- `BILI_RATELIMIT` 缺省值从 `0` 改为 `1.5` 秒（与 CI 既有配置一致——该值已在 CI 集成任务中长期验证安全）；环境变量覆盖语义（含设 0 关闭）保留；
- 循环遍历型用例（rank 全分区、parse_link 批量解析、互动视频图遍历）在循环体内加 `await asyncio.sleep(0.5)`（异步用例内异步休眠，符合宪法 I），并按 R8 缩减遍历规模。

**Rationale**: CI 的 1.5 秒是仓库内唯一有实证安全记录的间隔值；本地默认对齐 CI，消除"本地裸跑必触发 412"的隐患。

**预算核算**（cred0+cred1 ≤ 400 请求、≤ 30 分钟）:

- cred0 12 用例 ≈ 20 请求（明细见 data-model 预算表，以 data-model 为准）；
- cred1 重构后 ≈ 150 用例、平均 1.5–2 请求 ≈ 300 请求；合计 ≈ 320 ≤ 400 ✓；
- 时长：约 325 次间隔 × 1.5s ≈ 8 分钟纯休眠 + 请求耗时 ≈ 15–20 分钟 ≤ 30 分钟 ✓（BILI_RATELIMIT 可调大不破坏验收口径——验收按默认值计）。

**Alternatives considered**: 默认 1.0s（更快但无实证）；默认 0.5s（风控风险高）。

---

## R4: 顺序无关化策略（FR-009）

**Decision**: **生命周期合并**——把依赖跨用例全局变量传递资源 ID 的链式用例组合并为**单个生命周期用例**（用例内顺序天然合法，FR-009 约束的是跨用例依赖）：

| 现有链条（全局变量） | 合并后的单用例 |
|---|---|
| test_comment: send→reply→like→hate→delete（comment_id） | 一个"评论完整生命周期"用例 |
| test_favorite_list: create→set→modify→copy→move→clean→delete（media_id） | 一个"收藏夹完整生命周期"用例（读接口拆出独立用例） |
| test_watchroom: create→join→share→progress×2→close→msgs（room） | 一个"观影房间完整生命周期"用例 |
| test_vote: create→update（vote_id） | 一个"投票创建与更新"用例 |
| test_rank: get_music_rank_list→phase（phase_id） | 合并为单用例 |
| test_live: get_black_list→ban→unban（black_list） | 归 cred3，同样合并 |

**Rationale**: 合并把 N 个写操作收敛为一次完整闭环，同时满足顺序无关与降低请求 / 写操作总量两个目标；fixture 资源池方案仍隐含"先建后用"的执行顺序。

**Alternatives considered**: 每用例独立建资源（写操作次数 ×N，账号成本最高）；module 级 fixture 供资源（顺序依赖转移而非消除）。

---

## R5: cred2 公开发布类写操作目标改道（FR-008）

**Decision**: 评论生命周期用例的发布目标从第三方热门视频 av271 改为**共享账号自有视频**：

- 用例内动态获取：`get_self_info(credential)` 取自身 mid → `User(mid).get_videos()` 取第一个自有视频 aid 作为评论 oid（**不硬编码**任何 mid / aid，换号不失效）；
- 自有视频缺失时**条件跳过**并给出明确原因（跳过不属于失败，SC-001 口径为"除缺凭据外无跳过"仅约束 cred0——cred2 允许该条件跳过，在安全策略文档成文）。

**Rationale**: 2026-09-26 实测确认该账号持有 2 个自有视频，自有内容评论完全满足 FR-008；动态获取优于硬编码（账号轮换零维护）。

**Alternatives considered**: 指定一个专用第三方低热度视频（仍是公开他人内容，违反 FR-008 字面与精神）；维持 av271（公开刷评论是封号高危向量，直接违反规格）。

---

## R6: 弹幕与直播写操作归层

**Decision**:

- **视频弹幕发送**（`Video.send_danmaku`）：全库无 `delete_danmaku`（video.py / live.py 均无，已核查），无清理配对可能 → **cred3**；
- **直播弹幕发送、全部送礼**（金 / 银 / 背包 / 人气票）、**房管封禁 / 解封**、**直播预约创建**（对外可见的预约公告）→ **cred3**；
- **直播签到 dahanghai、领取奖励 receive_reward**：归入"自身状态类"白名单（见 R7）→ cred2。

**Rationale**: FR-006 要求六态（含弹幕）零残留；无删除 API 即无法达成，规格红线优先于覆盖便利。直播域是风控最激进域，从严归层。

**Alternatives considered**: 对自有视频发弹幕归 cred2（仍有残留，违反 FR-006）；弹幕用例直接删除（损失覆盖，cred3 门控保留更优）。

---

## R7: "自身状态类"白名单与资源消耗类边界

**Decision**: 安全策略定义五个操作类别（详见 data-model 的 Account Safety Policy 实体）：

1. **可逆写**（like / unlike、fav / unfav、follow / unfollow、评论 send / delete、toview add / remove、收藏夹 CRUD）→ cred2，配对恢复 + 断言；
2. **自身状态类**（直播签到、观看上报 report_watch_history / report_start_watching、互动视频评分 mark_score）：不可逆但**仅自身可见**、不属于六态清单、无对外发布形态 → cred2 允许，逐项成文于安全策略；
3. **资源消耗类**（投币 pay_coin、三连 triple、文章 / 音频投币）：消耗账号货币资源 → **cred3**；
4. **公开发布类**（评论、弹幕、私信 send_msg、投票创建、直播预约）：可对外可见；评论（自有内容）→ cred2，弹幕（无删除）/ 私信 / 投票（无删除）/ 直播预约 → cred3；
5. **破坏性 / 身份特定类**（clear_toview_list、delete_viewed_videos_from_toview、创作中心全量、房管操作）→ cred3。

**Rationale**: 类别化判据使全部归层决定可审计、可复用（新增用例按类别对号入座），避免逐例拍板。

**Alternatives considered**: 逐用例自由裁量（标准漂移）；一刀切全部写操作入 cred3（cred2 层失去存在意义，US3 落空）。

---

## R8: 爆发循环用例收敛（FR-010 / 预算）

**Decision**:

| 用例 | 现状 | 收敛方案 |
|---|---|---|
| rank `test_a`（24 个 RankType 全遍历） | 24 连发 | 采样 5 个代表分区（含默认 + 边缘类型）+ 循环内 0.5s 节流 |
| rank `test_i`（7 个 VIP 榜） | 7 连发 | 保留全量 + 节流（账号 VIP 有效，实测确认） |
| rank `test_j`（漫画全榜） | 连发 | 采样 3 个 + 节流 |
| root_functions `test_a`（约 40 个 URL 解析） | 40 连发 | 保留 20 个代表性 URL 形态 + 0.5s 节流 |
| interactive_video 图遍历 | 节点级连发 | 保留 + 节点间 0.5s 节流 |

**Rationale**: 采样保住"形态覆盖"（各 URL 形态 / 分区类型至少一个代表）而非"全量枚举"，与请求预算兼容；全量枚举对回归价值增量极低。

**Alternatives considered**: 全量保留仅加节流（请求预算超限，cred1 ≤400 无法达成）。

---

## R9: 请求预算核算与验收验证方法（SC-001 / SC-002 / SC-007）

**Decision**:

- **静态预算表**落在 data-model.md（每层用例数 × 估计请求数 → 层预算），作为映射方案的硬约束；
- **动态计数**：conftest 提供常驻 opt-in 计数器——`BILI_COUNT_REQUESTS=1` 时对网络层请求挂 session 级计数，会话结束时在终端摘要输出总请求数（不输出任何 URL 参数值之外的敏感信息，仅计数与域名汇总）。验收 SC-001 / SC-002 / SC-007 以该计数器读数为准。

**Rationale**: 预算必须可核验而非纸面承诺；opt-in 常驻（而非一次性 instrumentation）让任何人在任何时候都能复查预算，成本为一个环境变量开关。

**Alternatives considered**: 一次性验收脚本（验收后不可复验）；离线静态估算当验收（无实证）。

---

## R10: 既有分层瑕疵顺手修正

**Decision**:

- `test_initial_state.py`：纯本地解析用例，更名为 `test_offline_initial_state.py`（摘除 integration 标记与限速，符合宪法 IV）；
- `test_ass.py`：生成的字幕 / 弹幕文件改用 pytest `tmp_path` 写入，不再污染仓库工作目录。

**Rationale**: 均为分层测试原则（宪法 IV）的直接违例，属本特性"重组既有用例"范围内的顺带修正，单独立项不成比例。

**Alternatives considered**: 保持现状（宪法违例存续）。

---

## R11: 匿名集成用例与边界文件归属

**Decision**:

- 匿名集成用例（hot / rank 大部 / bangumi / article_category / video_zone / live_area / black_room / cheese / client / emoji / festival / game / video_uploader.get_missions / homepage 匿名部分）不强制分级，保持 `integration` 标记，默认运行照常执行；
- `test_creative_center.py` 整文件 → cred3（创作中心需 UP 主身份且规格 FR-007 明确归层）；
- `test_session.py`：9 个读接口 → cred1；`send_msg` → cred3（FR-007）；
- `test_readonly_smoke.py`：保持 `readonly` 模块标记（FR-013），其中需凭据用例附加 `cred0`。

**Rationale**: 分级义务仅覆盖"需要凭据的用例"（FR-001），匿名用例套分级徒增维护成本。

---

## R12: 宪法与门禁影响面

**Decision**:

- 不修宪：cred 分级是宪法 IV"分层测试"在凭据维度上的运行时细化，落在 AGENTS.md 测试节（FR-014）；
- `BILI_RATELIMIT` 缺省值变更属测试基础设施行为变更，同步更新 AGENTS.md 与 conftest docstring；
- 门禁影响：`uv run python scripts/lint.py` 须全绿；tests/scripts 阻断检查规则（lint.py 内置）如涉及测试文件命名 / 结构需同步核验；doc_gen 不涉及（测试函数非公共 API）；
- `.github/workflows/ci.yml` 的 `readonly` 任务行为不变（`pytest -m readonly` 照常）；schedule / manual 的 integration 任务建议后续切换到 cred0–cred2 口径（属 tasks 阶段决定，不破坏现有行为）。

---

## 结论

全部设计未知项已闭环：标记机制（R1）、漏标防护（R2）、限速默认（R3）、顺序无关策略（R4）、写目标改道（R5，自有视频实测确认）、高危归层（R6 / R7）、循环收敛（R8）、预算核验（R9）、分层瑕疵修正（R10）、匿名边界（R11）、宪法影响（R12）。可进入 Phase 1 设计产出。
