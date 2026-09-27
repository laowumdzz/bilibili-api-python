# Research: README 适配本 Fork 仓库并声明上游来源与 AI 维护

**Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)

Phase 0 事实核查。每项给出：结论（Decision）、依据（Evidence）、被否的备选（Alternatives）。全部依据来自仓库本地可验证事实（git / 配置文件 / 工作流），未依赖外部网络（会话期间 GitHub 直连超时，已尽量避免外部断言）。

## R1. 本项目实际仓库地址

**Decision**: README 中所有"本项目"指向 `https://github.com/laowumdzz/bilibili-api-python`。

**Evidence**: `git remote -v` 唯一远端为 `git@github.com:laowumdzz/bilibili-api-python.git`，且有活跃跟踪分支（`origin/main`、`origin/HEAD`）与全部发布 tag（v18.0.0 – v19.2.2）；git 提交人为 `laowumdzz`。

**Alternatives considered**:
- `AGENTS.md` 头部声明的 `https://github.com/LaowuClaw/bilibili-api-python` —— **否**。与 git remote 实态漂移（无法核实该地址现状，会话期间 GitHub 直连超时）。git remote 是机器可验证的强事实，散文声明不是。若属 GitHub 账号改名，旧地址会自动重定向，新地址仍然安全。
- ~~留待用户确认~~ **已裁决（2026-09-27，$speckit-checklist 澄清问答）**：维护者确认采用 `laowumdzz` 为权威地址。AGENTS.md 头部地址漂移仍记入遗留清单第 3 项，待后续提交统一修正 AGENTS.md。

## R2. 分发方式与安装指引

**Decision**: 安装指引 = ① 本仓库 git 安装（`pip install git+https://github.com/laowumdzz/bilibili-api-python.git@main`，或锁定 `@v19.2.2` 等 tag）；② 从 GitHub Release 下载 `uv build` 产物（sdist + wheel）本地安装。移除上游 PyPI 双包（`bilibili-api-python` / `bilibili-api-dev`）安装入口与对应徽章。

**Evidence**: `.github/workflows/python-publish.yml` 工作流名为 "Build and Attach to Release"，注释明确"仅发布到 GitHub Release，不再上传 PyPI"，构建步骤 `uv build --sdist --wheel` 后 `gh release upload`；版本号由 setuptools 动态读取 `BILIBILI_API_VERSION`（当前 19.2.2）。

**Alternatives considered**:
- 保留 PyPI 入口作为备选 —— **否**。上游 PyPI 包是上游代码的发布物，装到的不是本 fork；保留即违反 FR-003。
- 仅 git 安装不提 Release 资产 —— **否**。Release 资产（wheel/sdist）是本 fork 唯一的正式版本化发布物，离线/锁定版本场景需要它。

## R3. 注记原文与 commit SHA

**Decision**: 注记逐字使用用户提供的原文（含 38 位 SHA `027563d2fe7604967242986aac51d693c905`），不做截断/补全/改写；spec Edge Case 中"SHA 长度异常"疑点就此定案——**非笔误，系刻意原文**。

**Evidence**: 本仓库首条提交 `99648df` 的 message 逐字即"初始化bilibili-api-python仓库,Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支"。用户要求的注记与建仓记录同源。

**Alternatives considered**: 将 SHA 补全为 40 位或标注提醒 —— **否**。与建仓记录逐字一致优先于形式规范。

## R4. Logo 引用

**Decision**: logo 从上游 raw URL（`raw.githubusercontent.com/Nemo2011/bilibili-api/main/design/logo.png`）改为本仓库相对路径 `design/logo.png`。

**Evidence**: 本仓库 `design/` 目录实际存在 `logo.png`（及全套变体）；相对路径使 README 自包含，不受上游文件移动影响。

**Alternatives considered**: 沿用上游 raw URL —— **否**。上游路径变更会让本 fork README 挂图，且不必要地依赖上游仓库可用性。

## R5. 徽章与 Star History

**Decision**:
- 保留（改指本仓库）：CI 徽章 → 本仓库 `actions/workflows/ci.yml/badge.svg?branch=main`（ci.yml 在 push main/dev、PR、每周定时触发，徽章有效）；License 徽章；Python 版本徽章（3.10+）。
- 新增：GitHub Release 版本徽章（`img.shields.io/github/v/release/laowumdzz/bilibili-api-python`），替代被移除的 PyPI stable/pre-release 双徽章，标示当前版本 19.2.2 所在 Release。
- 移除：上游 Stars 徽章、上游 Star History 图（反映上游数据，对本 fork 失真且本项目暂无可观星数）。
- API 数量徽章（400+）：链接目标从上游 `data/api/` 目录改为本仓库同路径。

**Evidence**: `.github/workflows/ci.yml` 触发器覆盖 main push；`bilibili_api/data/api/` 在本仓库实际存在；tag `v19.2.2` 及其 Release 存在于本仓库远端。

**Alternatives considered**: Stars/Star History 改指本仓库 —— **否**。零星数据无展示价值，等有可观数据再恢复。

## R6. 文档站链接

**Decision**: "开发文档"链接保留上游 `https://nemo2011.github.io/bilibili-api`，但明确标注为"上游文档"；同时给出本仓库 `docs/` 目录入口作为本项目文档源。

**Evidence**: 本仓库 `docs/index.html`（docsify 配置）仍指向 `nemo2011/bilibili-api`，本 fork 未部署独立文档站；`docs/` 目录内容完整（含 API 文档生成物）。

**Alternatives considered**: 仅留上游链接不标注 —— **否**，违反 FR-002 三态规则；只留 `docs/` 目录链接 —— **否**，docsify 站的阅读体验对新手有价值，标注后保留是增量信息。

## R7. 开发/贡献指引

**Decision**: README 开发章节承载本项目真实工作流：`uv sync` → `uv run python install.py`（Git Hooks）→ `uv run python scripts/lint.py` 全量门禁；测试分层常用命令（无凭据 `uv run pytest -m "not integration"`；分层入口见 AGENTS.md）；Conventional Commits；PR 目标 `dev`。不再深链 `.github/CONTRIBUTING.md` 作为主指引。

**Evidence**: `install.py`、`scripts/lint.py`、`uv.lock` 均实际存在；宪法与 AGENTS.md 载明上述工作流；`.github/CONTRIBUTING.md` 为上游遗留（`git clone nemo2011` + pip 安装 + 向上游 dev 发 PR），与本 fork uv 工作流全面漂移。

**Alternatives considered**: 顺带重写 CONTRIBUTING.md —— **范围外**。spec 明确本特性只动 README；CONTRIBUTING.md 漂移记为后续独立事项（见 quickstart.md 遗留清单）。README 内联指引已足够自洽。

## R8. 上游致谢与许可证链

**Decision**: 保留现 README 的 MoyuScript 沿革说明（原仓库已删除 → nemo2011 fork → 首末 commit 链接）、GPLv3 注意事项段；与新增 fork 注记合并构成三级来源链。

**Evidence**: GPL-3.0-or-later 衍生作品的署名义务（宪法"许可证与用途"条）；`git log --reverse` 首条 `99648df` 印证 fork 事实。

**Alternatives considered**: 精简沿革说明 —— **否**。来源链是 fork 合规与致谢的核心，删除有违 FR-006。

## 遗留事项（范围外，供后续特性/提交处理）

1. `.github/CONTRIBUTING.md` 为上游遗留（pip 流程、指向 nemo2011），需按本 fork uv 工作流重写。
2. `docs/index.html` docsify 配置仍指向 nemo2011 仓库（"贡献项目"链接与 repo 字段），部署独立文档站时需一并迁移。
3. `AGENTS.md` 头部"上游仓库"地址（LaowuClaw）与 git remote（laowumdzz）漂移，需维护者确认后统一。
