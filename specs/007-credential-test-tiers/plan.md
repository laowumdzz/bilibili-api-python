# Implementation Plan: 集成测试按重要程度分级重构（凭证账号保护）

**Branch**: `007-credential-test-tiers` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-credential-test-tiers/spec.md`

## Summary

把约 200 个需凭据的集成用例按重要程度重构为四层（cred0 核心冒烟 ≤30 请求 / cred1 读回归、合计 ≤400 请求 / cred2 自清理写生命周期、六态零残留 / cred3 高危显式门控、默认收集即排除），配套：pytest marker + 收集期排除机制、漏标防护、默认限速 1.5s 与循环内节流、跨用例全局变量链合并为单生命周期用例、cred2 公开发布类写目标动态改道至账号自有视频（实测该账号持 2 个自有视频）。技术方案详见 [research.md](research.md)（R1–R12 全部未知项已闭环，无 NEEDS CLARIFICATION）。

## Technical Context

**Language/Version**: Python ≥ 3.10（uv 管理 `.venv`，实际解释器 3.14；代码须兼容 3.10，无更高版本独有特性）

**Primary Dependencies**: pytest + pytest-asyncio（asyncio_mode=auto）；被测库自身（bilibili_api）；无新增第三方依赖

**Storage**: N/A（测试基础设施改造；TEMP 凭据缓存文件沿用现有契约，不变）

**Testing**: 本特性**对象即测试套件**——pytest marker 体系 + conftest.py 钩子（pytest_collection_modifyitems / credential fixture / ratelimit fixture）；离线单测（test_offline_*）不受影响

**Target Platform**: 开发者本机（Windows / Git Bash 为主）+ GitHub Actions CI（readonly 任务为 PR 门禁；integration 任务为 schedule / manual）

**Project Type**: library（异步 API 库）的测试基础设施

**Performance Goals**: cred0+cred1 合计对外请求 ≤ 400 次、总时长 ≤ 30 分钟（默认限速 1.5s 口径）；全程零 412

**Constraints**: 单一共享测试账号（TEMP 缓存，mid=479269916，等级 5，VIP，2 个自有视频）；cred3 默认收集即排除且不在验收范围真机执行；凭据值不得出现在任何提交内容或日志输出

**Scale/Scope**: 38 个集成测试文件 / 313 用例的分层标注与约 30 个用例的重构（合并 / 改道 / 采样 / 节流）；conftest.py 增量改造；AGENTS.md 测试节更新

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 核查结论 |
|------|----------|
| I. 异步优先 | **PASS**。不修改库代码；用例内节流统一 `await asyncio.sleep()`（异步路径无同步阻塞）；既有 ratelimit fixture 的 `time.sleep` 位于同步 fixture（非异步路径），属现状模式沿用 |
| II. 声明式 API 定义 | **PASS / 不适用**。不新增业务 API、不改 data/api JSON |
| III. 质量门禁（不可协商） | **PASS（义务列明）**。`uv run python scripts/lint.py` 全绿为验收项（quickstart V7）；测试函数非公共 API，无 doc_gen 义务；tests/scripts 阻断检查随 tests 结构变更同步核验；不引入类型豁免 |
| IV. 分层测试（不可协商红线） | **PASS（本特性为其强化）**。离线 / readonly / 写三层边界不变；cred 分级是凭据维度细化；顺带修正两处既有违例（test_initial_state 更名离线化、test_ass 本地文件输出改 tmp_path）；缺凭据自动 skip 语义保留 |
| V. 兼容性与破坏性变更控制 | **PASS**。无库 API 变更；`BILI_RATELIMIT` 缺省 0→1.5 为测试基础设施行为变更，AGENTS.md 与 conftest docstring 同步说明；`pytest -m readonly` / `-m "not integration"` 语义不变 |
| 技术与安全约束 | **PASS**。凭据不出现在提交与日志（探针脚本仅在 TEMP 运行、仅输出 mid 与计数；请求计数器仅输出计数与域名汇总）；uv 管理环境不变 |

**Phase 1 设计后复评**: 分层映射表（data-model.md）与选择器契约（contracts/）未引入宪法违例——cred2 写用例全部经配对恢复或自身状态类白名单成文；cred3 收集即排除满足"保护测试账号不被风控"的宪法 IV Rationale；无新增豁免、无绕过门禁的设计。**门禁复评通过，无 Complexity Tracking 事项。**

## Project Structure

### Documentation (this feature)

```text
specs/007-credential-test-tiers/
├── plan.md                        # 本文件
├── research.md                    # Phase 0：R1–R12 设计决策
├── data-model.md                  # Phase 1：Tier / 安全策略实体 + 38 文件权威映射表
├── quickstart.md                  # Phase 1：V1–V7 验证指南
├── contracts/
│   └── test-tier-selection.md     # Phase 1：层级选择器接口契约
└── tasks.md                       # Phase 2（$speckit-tasks 生成，非本命令产物）
```

### Source Code (repository root)

```text
pyproject.toml                     # [tool.pytest.ini_options] 注册 cred0–cred3 marker
tests/
├── conftest.py                    # ① 收集期 cred3 排除 + 剔除计数提示（漏标/错标检查先于剔除执行）
│                                  # ② 收集期漏标/错标防护（fixturenames 闭包，warn / BILI_STRICT_TIERS=1 收集错误）
│                                  # ③ BILI_RATELIMIT 缺省 0→1.5
│                                  # ④ BILI_COUNT_REQUESTS=1 请求计数器与 412 类风控统计
│                                  #    （含 BILI_ABORT_ON_RISK=1 首个风控响应即中止会话）
├── test_offline_initial_state.py  # 由 test_initial_state.py 更名（宪法 IV 修正）
├── test_readonly_smoke.py         # 附加 cred0 标记（readonly 保留）
├── test_video.py / test_user.py / test_live.py / test_dynamic.py / test_comment.py /
│ test_favorite_list.py / test_session.py / test_rank.py / test_article.py / test_audio.py /
│ test_topic.py / test_video_tag.py / test_manga.py / test_watchroom.py /
│ test_interactive_video.py / test_vote.py / test_creative_center.py
│                                  # 按映射表分层标注；生命周期合并 / 写目标改道 / 循环采样节流
├── test_root_functions.py         # parse_link 采样 + 节流
├── test_ass.py                    # 输出改 tmp_path
└── （其余匿名只读文件不动）
AGENTS.md                          # 测试节：四级体系、命令矩阵、账号安全策略、限速默认值、已知集成覆盖缺口（login_v2 / video_uploader 追踪去向）
```

**Structure Decision**: 单项目（库）结构，全部改造收敛于 `tests/`、`pyproject.toml` 与 `AGENTS.md`，不移动文件目录（最小 diff，保留 git 历史）。

## Complexity Tracking

> 无宪法违例需豁免，本节为空。
