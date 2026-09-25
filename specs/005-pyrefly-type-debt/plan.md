# Implementation Plan: 清零 pyrefly 存量类型错误（1064 条）

**Branch**: `005-pyrefly-type-debt` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-pyrefly-type-debt/spec.md`

## Summary

把 2026-09-25 实测的 1064 条 pyrefly 存量类型错误（9 个豁免码 1061 条 +
残留码 3 条，分布于 60 个文件）全部清零，并将 9 条豁免条目与棘轮基线
全部退役，使类型门禁恢复全额默认拦截。

研究阶段（[research.md](research.md)）的核心发现：存量并非 1064 个孤立
问题——约 6 成直接或间接源于单一系统性根因（`Api.request()/result` 的
`int | str | dict | bytes | None` 联合返回类型向全库约 380 个
`-> dict` 函数及下游局部变量传导），其余聚集于 `_live_danmaku.py` 的
protobuf 解码累加器（67 条）与约 40–60 条真 bug / 注解错误（含 2 处
已核实的漏 `await` 运行时 bug）。技术路线据此定为：**中心化类型收窄
访问器（地基）→ 按模块清扫迁移 → 收尾退役豁免机制**，批次按根因/模块
切分，验收台账按错误码记账（棘轮天然按码计数），每批次独立门禁全绿、
棘轮只降不升、公共 API 零破坏。

## Technical Context

**Language/Version**: Python ≥ 3.10（必须兼容 CPython 3.10，禁用更高版本
独有特性；类型修复使用 `typing.cast` / `X | Y` 联合 / isinstance 收窄，
均为 3.10 可用）

**Primary Dependencies**: 现有依赖不动。类型工具链为 pyrefly 1.2.0
（uv.lock 实锁；pyproject 为宽松 `>=0.1`，特性期间不升级，见
research.md R4）+ ruff（check/format）

**Storage**: N/A（无运行时存储；台账载体为 `scripts/type_ratchet.py`
常量与 `pyproject.toml` 配置，见 [data-model.md](data-model.md) 存储映射）

**Testing**: pytest + pytest-asyncio；每批次跑离线子集
`uv run pytest -m "not integration"`；不新增集成用例（类型修复无新增
网络面）

**Target Platform**: 任意 Python 3.10+ 平台（纯库源码静态层修复，
无平台差异）

**Project Type**: library（异步 API 封装库；本特性不触碰 HTTP/客户端层）

**Performance Goals**: N/A（静态注解变更，无运行时性能目标；唯一性能
约束：门禁链路不增加新步骤，棘轮命令口径不变）

**Constraints**: 公共 API 零破坏（[contracts/public-api-compatibility.md](contracts/public-api-compatibility.md)）；
cast 仅限中心收窄点与逐处论证的误报（spec FR-004）；禁 `asyncio.run()`；
错误码清零与豁免退役必须同批次成对（宪法 III）

**Scale/Scope**: 1064 条错误 / 60 文件 / 9+2 错误码；tasks.md 定案：19 个
模块清扫批次（T004–T022）+ 校准/地基/试点各 1（T001–T003）+ 先行提交
窗口（T026–T034）+ 终态收口（T023–T025、T035–T037）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | 宪章原则 | 状态 | 说明 |
|---|----------|------|------|
| I | 异步优先 | ✅ 通过 | 纯类型层修复；不新增 `asyncio.run()`、同步阻塞或绕过 `BiliAPIClient` 的访问；`Api` 访问器为 `async def` |
| II | 声明式 API 定义 | ✅ 通过 | 不改 `data/api/*.json`，不改 `Api(**api).update_params(**params).result` 调用链形态（访问器是链尾的增量替换选项） |
| III | 质量门禁 | ✅ 通过 | 本特性即宪法 III 存量处置义务的执行：每批次 `lint.py` 全绿、棘轮只减不增、清零码同批移除豁免、公共符号 docstring/注解齐全后 `doc_gen.py` 再生 |
| IV | 分层测试 | ✅ 通过 | 仅离线用例参与批次验收；不触碰凭据、网络与账号状态 |
| V | 兼容性与破坏性变更控制 | ✅ 通过（有看护点） | 零破坏目标，兼容雷区已识别并有预案（[contracts/public-api-compatibility.md](contracts/public-api-compatibility.md)；research.md R6）；真 bug 按"一事一提交"拆分 |
| — | 技术与安全约束 | ✅ 通过 | 不涉及凭据；调试不用 print；3.10 语法约束已在 Technical Context 固化 |

**Phase 1 设计后复检**：地基设计（`Api` 增量访问器 + 中心收窄）为纯
增量公共 API；`Api.result` 原样保留；`session.py:465` 处置预案默认走
"对齐 + 兼容垫层"而非破坏性改名；无新依赖、无新门禁步骤、无豁免新增。
**无违规，无需 Complexity Tracking 豁免论证。**

## Project Structure

### Documentation (this feature)

```text
specs/005-pyrefly-type-debt/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
│   ├── public-api-compatibility.md   # 库对外接口兼容契约
│   └── gate-tooling.md               # 类型门禁终态/中间态契约
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
bilibili_api/
├── utils/
│   └── _api.py               # 批次 1 地基：Api 类型化结果访问器 + 中心收窄
│   └── _live_danmaku 相关解码在 _live_danmaku.py（根因 B，67 条聚集）
├── login_v2.py               # 批次切分第一梯队（73 条）
├── user.py / live.py / bangumi.py / video.py     # 60-65 条级
├── video_uploader.py / dynamic.py / cheese.py / watchroom.py / audio_uploader.py
├── （其余 ~50 个文件按根因聚簇并入相邻批次）
├── channel_series.py:231     # 真 bug（漏 await），独立修复提交
└── session.py / video_uploader.py               # 残留码 3 条 + 兼容雷区

pyproject.toml                # [tool.pyrefly.errors] 豁免表逐条退役至空
scripts/type_ratchet.py       # BASELINE 逐批下调至空 + KNOWN_RESIDUAL 清理
docs/modules/                 # doc_gen.py 再生产物（禁手编）
tests/                        # 仅消费既有离线用例，预计无新增
```

**Structure Decision**: 单项目结构（库本体原地修复，无新目录）。
批次 1 的地基落在 `utils/_api.py`（反爬/请求核心，与 AGENTS.md 架构一致：
类型收窄属于请求链路层，不得散落到业务模块）；模块清扫批次逐文件推进，
每文件一次触碰完成"调用点迁移 + 该文件根因 B/C 修复"，避免同文件多批次
反复 rebase。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无违规。本特性为存量削减型工作，不引入新复杂度；唯一新增面（`Api` 类型化
访问器）是宪法 II 既有调用链的增量延伸，已在 contracts 中约束为纯增量。
