# Contract: README 内容契约（readme-content）

**Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md) | **归属底册**: [data-model.md](../data-model.md)

README 是本仓库对外的门面契约：访客依赖它获取来源、安装、开发三类事实。本契约固定其必须满足的不变量；元素级处置细则以 data-model.md 实例清单为准，二者冲突时以本契约为准并回改清单。

## C1. 注记（不变量，最高优先级）

README 首屏显著位置（标题区之后、正文首章节之前，无需滚动或极少滚动可见）必须包含以下原文，逐字保留（空格、标点、SHA 均不得改动）：

```text
本项目Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支并由AI维护
```

- 校验：以上述字符串做固定字符串精确匹配，至少命中 1 次。
- 该注记与建仓首提交 `99648df` 的 message 同源；SHA 长度非标准 40 位属刻意原文。

## C2. 本项目地址（唯一权威值）

所有 `SELF` 态引用统一使用：

```text
https://github.com/laowumdzz/bilibili-api-python
```

- git 协议形式（clone 示例）可用 `git@github.com:laowumdzz/bilibili-api-python.git` 或对应 https 形式。
- 该值以 git remote 实态为准（research.md R1）；若维护者确认为其他门面地址，全局替换本常量并同步本契约。

## C3. 归属三态（完备性）

README 中每一处 URL、徽章、图片、仓库指向、文档链接必须满足且仅满足：

1. **SELF**：指向 C2 地址或本仓库内实际存在的相对路径；
2. **UPSTREAM_LABELED**：指向 nemo2011 / MoyuScript 资源，且伴随可见的"上游"语义标注；
3. **REMOVED**：已从全文消失（精确字符串零命中）。

禁止第四态：未标注的上游归属引用。校验方式：全文清点 + 与 data-model.md 实例清单逐条核销。

## C4. 安装契约

README 给出的每条安装命令，装到的必须是**本仓库的代码**。允许的形态：

- `pip install git+https://github.com/laowumdzz/bilibili-api-python.git@<tag|main>`
- 从本仓库 GitHub Release 下载 sdist/wheel 后本地安装

禁止形态：将 `pip install bilibili-api-python` / `bilibili-api-dev`（上游 PyPI 包）表述为本项目的安装方式。

## C5. 事实正确性

- 版本相关表述与 `BILIBILI_API_VERSION` 当前值不冲突（优先用徽章等动态来源，避免手写死版本号）。
- 示例代码仅使用库中实际存在的 API 与当前签名（关键字传参），可原样运行。
- 开发指引命令序列：`uv sync` → `uv run python install.py` → `uv run python scripts/lint.py`；测试入口 `uv run pytest -m "not integration"`（无凭据）——每条命令须真实可用。
- 提交规范（Conventional Commits）与 PR 目标分支（`dev`）的表述与项目 Git Hook / AGENTS.md 一致。

## C6. 安全与合规

- 全文不得出现真实凭据值（SESSDATA / bili_jct 等仅以占位符变量名出现）。
- GPL-3.0-or-later 许可证声明与"仅限学习测试、禁止滥用"注意事项保留。
- 来源致谢链保留：MoyuScript 原仓库 → nemo2011 fork（含首末 commit 链接与沿革说明）→ 本 fork 注记。

## C7. 渲染有效性

- GFM 语法正确（表格、脚注、徽章在 GitHub 渲染无残缺）。
- 相对路径引用（`design/logo.png`、`LICENSE`、`docs/`、`bilibili_api/data/api/`）在仓库中实际存在。
- 绝对链接（上游文档站、上游仓库、shields.io 徽章）格式合法；上游链接按 C3-2 标注。
