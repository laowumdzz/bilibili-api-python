# Implementation Plan: README 适配本 Fork 仓库并声明上游来源与 AI 维护

**Branch**: `008-readme-fork-notice` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-readme-fork-notice/spec.md`

**Note**: 本项目维护者既有实践为本地 `main` 直提交（宪法开发工作流第 1 条允许维护性直提交）；Branch 字段仅承载特性目录标识，不强制切分支。

## Summary

将仓库根 `README.md` 从上游 `nemo2011/bilibili-api` 的原样继承态改造为本 fork 实态：首屏逐字嵌入建仓注记（Fork 来源 + commit SHA + AI 维护，与建仓首提交 `99648df` 的信息逐字一致）；全部仓库归属引用按"本项目 / 明确标注的上游 / 移除"三态清理；安装指引改为本仓库 git 安装与 GitHub Release 资产（本 fork 不上 PyPI，`python-publish.yml` 仅挂 Release）；开发/贡献指引改为本项目 uv 工作流；保留 GPL-3.0 声明与 MoyuScript → nemo2011 → 本项目的来源致谢链。纯文档改造，不触碰库代码。

## Technical Context

**Language/Version**: Markdown（GitHub Flavored，中文为主）；所述事实基于 Python ≥ 3.10（`pyproject.toml` `requires-python = ">=3.10"`）、当前版本 19.2.2（`bilibili_api/__init__.py` 的 `BILIBILI_API_VERSION`）

**Primary Dependencies**: 无新增依赖。涉及的事实源：`pyproject.toml` / `uv.lock`（uv 管理）、`.github/workflows/ci.yml`（CI 徽章）、`.github/workflows/python-publish.yml`（分发方式：`uv build` sdist + wheel 仅挂 GitHub Release，明确"不再上传 PyPI"）、`design/logo.png`（本地 logo 资产）

**Storage**: N/A（纯文档）

**Testing**: 无新增自动化测试；验收为文档级校验（精确字符串比对、链接归属清点、干净环境实操）+ 实现后 `uv run python scripts/lint.py` 全绿确认（README 不在 doc_gen 生成范围，预期零影响）

**Target Platform**: GitHub 仓库首页 / README 渲染（GFM）；PyPI 项目页不适用（本 fork 不发布 PyPI）

**Project Type**: 库（library）的仓库门面文档改造

**Performance Goals**: N/A

**Constraints**: 注记原文逐字保留（含 38 位 SHA `027563d2fe7604967242986aac51d693c905`，与建仓首提交一致，系刻意原文非笔误）；不得出现任何真实凭据；GPL-3.0-or-later 声明与上游致谢链保留

**Scale/Scope**: 单文件 `README.md` 全文改造 + 附带引用清理；不改 `docs/`（工具链生成域）、不改 `.github/CONTRIBUTING.md`（已漂移，列为范围外后续事项）、不改库代码

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章原则 | 评估 | 结论 |
|---|---|---|
| I. 异步优先 | 不触碰库代码，README 示例沿用现行异步用法（`asyncio.run(main())` 由调用方启动） | ✅ 通过 |
| II. 声明式 API 定义 | 不新增/修改 API | ✅ N/A |
| III. 质量门禁 | README 位于仓库根，不在 `doc_gen.py` 生成范围（生成域为 `docs/modules/`），允许手工编辑；实现后仍须跑 `scripts/lint.py` 确认全绿无意外影响 | ✅ 通过 |
| IV. 分层测试 | 不新增测试代码；README 中的示例代码须与库当前真实用法一致，不得演示不存在的 API | ✅ 通过 |
| V. 兼容性与破坏性变更 | 纯文档，无接口变更；提交类型 `docs`，符合 Conventional Commits | ✅ 通过 |
| 凭据安全红线 | FR-008 明令 README 禁止出现真实凭据，示例仅用占位符 | ✅ 通过 |
| 许可证义务 | FR-006 保留 GPL-3.0-or-later 声明与完整来源链（fork 署名义务） | ✅ 通过 |

**无违规项，无需 Complexity Tracking 表。**

## Project Structure

### Documentation (this feature)

```text
specs/008-readme-fork-notice/
├── plan.md              # 本文件 ($speckit-plan command output)
├── research.md          # Phase 0 事实核查与决策 ($speckit-plan)
├── data-model.md        # Phase 1：README 引用归属清单模型 ($speckit-plan)
├── quickstart.md        # Phase 1：验收实操指南 ($speckit-plan)
├── contracts/
│   └── readme-content.md # Phase 1：README 内容契约（注记原文/三态归属/章节清单）($speckit-plan)
└── tasks.md             # Phase 2 output ($speckit-tasks - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
README.md               # 唯一改动目标（全文改造）
design/logo.png          # 既有本地资产，README logo 引用从上游 raw URL 改为该相对路径（不修改文件本身）
```

**Structure Decision**: 纯文档特性，无源码/测试结构变更；改动收敛于仓库根 `README.md` 单文件，`design/` 仅为引用目标。`docs/`（doc_gen 生成域）与 `.github/CONTRIBUTING.md`（上游遗留，pip 流程 + nemo2011 链接，与本 fork uv 工作流漂移）明确排除在外，后者在 research.md 记为后续事项。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无违规项，本表留空。
