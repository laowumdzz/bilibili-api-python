---
description: "Task list for feature 008: README 适配本 Fork 仓库并声明上游来源与 AI 维护"
---

# Tasks: README 适配本 Fork 仓库并声明上游来源与 AI 维护

**Input**: Design documents from `/specs/008-readme-fork-notice/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/readme-content.md, quickstart.md ✅ 全部就绪

**Tests**: 规格未请求自动化测试；验收为文档级校验（quickstart.md V1–V6），映射到各故事验收任务与 Polish 阶段。

**Organization**: 按用户故事分组（US1 来源注记与首屏归属 / US2 安装与快速上手 / US3 开发贡献工作流），每个故事可在其 Checkpoint 独立验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)
- 本特性为**单文件改造**（仓库根 `README.md`）：编辑类任务一律串行执行，仅校验类任务（不改文件）标 [P]

## Path Conventions

- 唯一编辑目标：`README.md`（仓库根）
- 参照产物：`specs/008-readme-fork-notice/`（data-model.md 为元素底册 E01–E32，contracts/readme-content.md 为内容契约 C1–C7，research.md 为决策 R1–R8，quickstart.md 为验收 V1–V6）
- 权威地址常量（契约 C2）：`https://github.com/laowumdzz/bilibili-api-python`（维护者 2026-09-27 已裁决）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 基线确认，防止带着错误前提开工

- [X] T001 基线确认：通读仓库根 README.md 现状；核对相对路径资产实际存在（design/logo.png、LICENSE、docs/、bilibili_api/data/api/）；确认权威地址采用 laowumdzz（契约 C2，research R1 已裁决）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 归属底册补全——所有处置的唯一事实源

**⚠️ CRITICAL**: 未完成本阶段不得开始任何用户故事的编辑

- [X] T002 全文引用清点登记：对照 specs/008-readme-fork-notice/data-model.md 的 E01–E32 实例清单逐条核销现 README.md，发现未登记的 URL / 徽章 / 图片 / 仓库指向 / 文档链接时，先补登记进 data-model.md（含 disposition 三态判定）再进入后续阶段——禁止未登记处置（data-model 状态迁移规则）

**Checkpoint**: 底册完备，三态清点口径闭合

---

## Phase 3: User Story 1 - 来源注记与首屏归属 (Priority: P1) 🎯 MVP

**Goal**: 访客首屏即可获知 fork 来源仓库、精确 commit SHA、AI 维护三个事实，且首屏所有归属引用三态归位

**Independent Test**: quickstart V1（注记逐字比对）+ V2 部分（首屏元素 REMOVED 零命中）；spec US1 验收场景 1–3

### Implementation for User Story 1

- [X] T003 [US1] logo 引用改为仓库内相对路径 `design/logo.png`（README.md 首行，E01，research R4）
- [X] T004 [US1] 标题改为 `bilibili-api-python`（README.md 标题区，E02，与仓库名一致）
- [X] T005 [US1] 徽章区三态处置（README.md 徽章区）：API 数量徽章链接改本仓库 `bilibili_api/data/api/`、LICENSE 徽章改本仓库 `LICENSE`（E03/E04，python 版本徽章 E05 保留）；移除 PyPI stable / pre-release 双徽章与 Stars 徽章（E06/E07/E08，research R2/R5）；Testing 徽章改本仓库 `ci.yml` `branch=main`（E09）；新增 GitHub Release 版本徽章（E10，`img.shields.io/github/v/release/laowumdzz/bilibili-api-python`）
- [X] T006 [US1] 注记嵌入（README.md 首屏，E12）：契约 C1 原文块逐字复制——"本项目Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支并由AI维护"——置于标题/徽章区之后、首个一级章节之前；SHA 为 38 位刻意原文，禁止截断/补全/改写（research R3 定案）
- [X] T007 [US1] 仓库行与沿革整合（README.md 头部链接区）："Github 仓库"行改为 laowumdzz 地址（E16）；MoyuScript 原仓库说明与首末 commit 链接保留并明确"上游"标注（E15/E17），与注记构成三级来源链；使用注意事项段保留（E13，GPL 义务）
- [X] T008 [US1] US1 验收：执行 quickstart V1（`grep -cF` 注记原文 ≥ 1 + 首屏位置目检）；REMOVED 复核——`pypi.org/project/bilibili-api`、`nemo2011/bilibili-api/stargazers`、`raw.githubusercontent.com/Nemo2011` 在 README.md 精确零命中

**Checkpoint**: MVP 达成——注记与首屏归属独立可验收，本故事单独交付即满足用户显式核心诉求

---

## Phase 4: User Story 2 - 安装与快速上手 (Priority: P2)

**Goal**: 新用户按 README 在干净 Python ≥ 3.10 环境装到本仓库代码并原样跑通首个示例

**Independent Test**: quickstart V4（干净环境安装 + 示例运行，含无网降级路径）；spec US2 验收场景 1–3

### Implementation for User Story 2

- [X] T009 [US2] 简介/特色事实核对（README.md 简介与特色章节，E18/E19）：覆盖范围、异步、三客户端、BV/AV、反爬表述与 AGENTS.md 概览及库现状一致，删失真表述
- [X] T010 [US2] 安装段改写（README.md 快速上手安装代码块，E20）：改为 ① `pip install git+https://github.com/laowumdzz/bilibili-api-python.git@main`（及 `@v19.2.2` 等 tag 锁定式）② 从 GitHub Release 下载 sdist/wheel 本地安装；移除上游 PyPI 双包三行（契约 C4 禁止形态）
- [X] T011 [US2] 版本警示适配（README.md 顶部 callout，E11）："接口可能改动请及时更新"保留，版本指向从 PyPI 徽章改为 Release 徽章；全文不手写死版本号（契约 C5，防与 BILIBILI_API_VERSION 漂移）
- [X] T012 [US2] 请求库自装说明核对（README.md，E21）：aiohttp / httpx / curl_cffi 三选一说明与现实现一致，顺带清理 `"curl_cffi"` 多余引号
- [X] T013 [US2] 示例代码核对（README.md 两处 Python 示例，E22/E23/E24）：`video.Video(bvid=...)` / `await v.get_info()` / `Credential(sessdata=..., bili_jct=..., buvid3=...)` / `await v.like(True)` 与现行签名一致（关键字传参）；占位符变量注明取值途径（get-credential 文档，链接标注上游）；凭据泄露 Warning 保留
- [X] T014 [US2] US2 验收：执行 quickstart V4——干净 venv 安装（git 式或 Release 资产式任一）+ 原样运行视频信息示例；无网环境按降级路径（Release 资产存在性核验 + 本地 `uv build` 产物安装 + 离线导入检查）

**Checkpoint**: US1 + US2 均可独立验收；README 已可支撑新用户完整上手

---

## Phase 5: User Story 3 - 开发与贡献工作流 (Priority: P3)

**Goal**: 开发者按 README 一次性完成环境搭建、检查、测试入口并知道 PR 去向（dev 分支）

**Independent Test**: quickstart V5（按章节原样执行 uv sync → install.py → lint.py → pytest）；spec US3 验收场景 1–3

### Implementation for User Story 3

- [X] T015 [US3] 异步迁移段处置（README.md，E25）：正文保留，sync-executor 链接明确标注"上游文档"
- [X] T016 [US3] 请求库选择段核对（README.md，E26）：`select_client(...)` 与 `request_settings.set("impersonate", ...)` 示例与现行 API 一致
- [X] T017 [US3] FAQ 逐条处置（README.md FAQ，E27/E29）：指名传参、412/代理条目保留；自定义请求库链接标注上游；"提 Issue"入口改本仓库 issues
- [X] T018 [US3] 贡献指引改写（README.md FAQ 贡献条目，E28，research R7）：clone 本仓库 → `uv sync` → `uv run python install.py`（Git Hooks）→ 分支开发 → PR 到 `dev`；提及 Conventional Commits；不深链已漂移的 `.github/CONTRIBUTING.md`；补充无凭据测试入口 `uv run pytest -m "not integration"`
- [X] T019 [US3] 脚注与引用定义块清理（README.md 文末，E30/E31）：代码来源脚注 [^1]–[^5] 全部保留（致谢义务）；引用定义块移除 stargazers / pypi / pypi-dev 三项，issues-new 改指本仓库，docs 系链接标注上游
- [X] T020 [US3] US3 验收：执行 quickstart V5——README 开发章节命令序列在本地新克隆工作副本上原样跑通至 lint 门禁

**Checkpoint**: 三个故事全部独立可验收

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 全文级收尾与门禁

- [X] T021 全文三态终清点（quickstart V2）：`grep -noE` 提取 README.md 全部 URL/徽章，逐条对 data-model.md E01–E32 核销三态归属；REMOVED 项零命中复核；剩余 nemo2011 / MoyuScript 引用 100% 伴随"上游"语义标注（spec SC-002）
- [X] T022 [P] 相对路径与渲染校验（quickstart V3）：`design/logo.png` / `LICENSE` / `docs/` / `bilibili_api/data/api/` 存在性；GitHub 渲染目检——徽章成图、脚注可跳转、注记中文与 SHA 无乱码（契约 C7）
- [X] T023 [P] 凭据零出现扫描与排版通查（spec FR-008 / 契约 C6 / checklist CHK022）：README.md 无真实凭据值形态字符串（示例仅占位符变量名）；全文中英文混排半角空格符合项目排版规范（AGENTS.md 约定）
- [X] T024 门禁回归（quickstart V6）：`uv run python scripts/lint.py` 全绿——README 不在 doc_gen 生成域，预期零影响，若报错即为阻断缺陷
- [X] T025 提交与知会：以 `docs: ...` Conventional Commits 提交（单提交单事）；向维护者知会范围外遗留（research.md 遗留清单：CONTRIBUTING.md 上游遗留重写、docs/index.html docsify 配置迁移、AGENTS.md 仓库地址漂移），不在本提交处理

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1；**阻塞全部用户故事**（底册未闭合不得编辑）
- **User Stories (Phase 3–5)**: 均依赖 Phase 2；因单文件目标，推荐按优先级串行（US1 → US2 → US3），每个 Checkpoint 独立验收
- **Polish (Phase 6)**: 依赖全部所选用户故事完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 后即可开始，不依赖其他故事——单独交付即 MVP
- **US2 (P2)**: Phase 2 后逻辑上独立；实操上与 US1 共享 README.md，建议在 US1 之后串行编辑避免冲突
- **US3 (P3)**: 同上，建议最后编辑

### Within Each User Story

- 编辑任务按任务号顺序执行（同一文件自上而下）
- 每故事末尾的验收任务（T008/T014/T020）通过后方可进入下一故事

### Parallel Opportunities

- 仅 T022 与 T023 为纯校验任务（不改文件）可并行
- 其余任务均编辑 README.md 同一文件，**不并行**；多人协作时按故事分工接力而非同时编辑

---

## Parallel Example: Polish 阶段

```bash
# 两个纯校验任务可同时进行：
Task: "T022 相对路径与渲染校验（V3）"
Task: "T023 凭据零出现扫描与排版通查（FR-008/CHK022）"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup（T001）
2. Complete Phase 2: Foundational（T002）
3. Complete Phase 3: User Story 1（T003–T008）
4. **STOP and VALIDATE**: V1 注记逐字比对 + 首屏三态核验
5. 此时已满足用户显式核心诉求（注记 + 来源声明），可先行提交交付

### Incremental Delivery

1. Setup + Foundational → 底册闭合
2. + US1 → 注记与首屏归属（MVP！）
3. + US2 → 安装与快速上手适配
4. + US3 → 开发贡献工作流指引
5. Polish → 终清点 + 门禁 + 提交

---

## Notes

- [P] 仅标校验类任务；编辑任务全部串行（单文件特性）
- [Story] 标签映射 spec.md 用户故事，便于追溯
- 注记原文以契约 C1 的代码块为唯一复制源，杜绝手敲变形
- REMOVED 判定一律以精确字符串零命中复核，不以肉眼为准
- 每个故事 Checkpoint 可停下独立验收；提交粒度遵循"一个提交只做一件事"（宪章 V）
- Avoid: 未登记处置、逐字注记被"规范化"、手写死版本号

---

## Phase 7: Convergence

- [X] T026 裁决并落实 dev 分支策略：远端无 dev 分支（`git ls-remote --heads origin dev` 为空），README.md 快速上手的 `@dev` 安装行当前不可执行、FAQ 贡献指引的 PR 目标 dev 分支不存在（主安装路径 @main/@tag/Release 不受影响）。二选一：创建远端 dev 分支使 FR-005 / 契约 C5 表述成立；或为 `@dev` 行加"待 dev 分支建立后可用"限定并使分支指引与本仓库实际工作流一致（如需偏离 AGENTS.md 的 dev 约定，同步修订 AGENTS.md 并在提交说明） per SC-003/FR-005 (partial)
