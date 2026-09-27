# Data Model: README 引用归属清单

**Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本特性为纯文档改造，无运行时数据实体。这里的"数据模型"是 README 内容元素的**归属清单模型**：把现 README 全文拆解为可枚举的元素，每个元素赋予三态归属之一，作为 FR-002 / SC-002 逐条清点的权威底册（contracts/readme-content.md 是其对外契约形式）。

## 实体：README 元素（ReadmeElement）

| 字段 | 说明 |
|---|---|
| `id` | 清单序号（E01, E02, …） |
| `kind` | 枚举：`title` / `badge` / `link` / `image` / `section` / `code-sample` / `footnote` / `callout` |
| `current` | 现状（现 README 中的形态与指向） |
| `disposition` | 三态枚举（见下） |
| `target` | 改造后的目标形态（REMOVED 时为空） |

### 归属三态（disposition 枚举，对应 FR-002）

| 值 | 语义 | 校验方式 |
|---|---|---|
| `SELF` | 指向本项目实际地址（`laowumdzz/bilibili-api-python`）或本仓库内相对路径 | 链接/徽章目标字符串含本仓库地址或存在的相对路径 |
| `UPSTREAM_LABELED` | 明确保留的上游资源，伴随可见的"上游"标注 | 元素文本含上游标注且指向 nemo2011 / MoyuScript 域 |
| `REMOVED` | 从 README 移除 | 精确字符串搜索零命中 |

### 校验规则（对应 SC-001 / SC-002）

- 全文 URL / 徽章 / 图片引用逐条登记，每条必居三态之一；未登记或双态的引用即验收失败。
- 注记（E12）为特殊元素：唯一采用"逐字原文"校验的元素（精确字符串比对，含标点与 SHA）。
- `SELF` 的相对路径目标必须实际存在于仓库（如 `design/logo.png`、`LICENSE`、`docs/`）。
- 全文不得出现真实凭据值（SESSDATA 形态的长随机串等）。

## 实例清单（现 README → 目标态）

> 本清单为权威底册；实现时若发现遗漏元素，须先补登记再处置（禁止未登记处置）。

| id | kind | current | disposition | target |
|---|---|---|---|---|
| E01 | image | logo 指向上游 raw URL `raw.githubusercontent.com/Nemo2011/.../design/logo.png` | SELF | 相对路径 `design/logo.png` |
| E02 | title | `# bilibili-api` | SELF | `bilibili-api-python`（与仓库名一致） |
| E03 | badge | API 数量 400+ → 上游 `data/api/` 目录 | SELF | 链接改本仓库 `bilibili_api/data/api/` |
| E04 | badge | LICENSE GPLv3+ → 上游 LICENSE | SELF | 链接改本仓库 `LICENSE` |
| E05 | badge | python 3.10+（无仓库指向） | SELF | 保留原样 |
| E06 | badge | PyPI stable 版本徽章 | REMOVED | —（本 fork 不上 PyPI，R2） |
| E07 | badge | PyPI pre-release 徽章 | REMOVED | —（同上） |
| E08 | badge | Stars 徽章（上游仓库星数） | REMOVED | —（上游数据失真，R5） |
| E09 | badge | Testing 徽章（上游 CI dev 分支） | SELF | 改本仓库 `ci.yml` `branch=main` |
| E10 | badge | （无） | SELF | 新增 GitHub Release 版本徽章（补位 E06/E07 的版本展示） |
| E11 | callout | "接口可能改动请及时更新"警示（带上游 PyPI 徽章） | SELF | 保留警示，版本徽章改指 Release |
| E12 | callout | （无） | SELF | **新增 fork 注记**：用户原文逐字嵌入首屏（R3 定案，逐字校验） |
| E13 | section | 使用注意事项（学习测试限定、滥用免责） | SELF | 保留（宪法许可证义务） |
| E14 | link | 开发文档 → 上游 docsify 站 | UPSTREAM_LABELED | 标注"上游文档"，另加本仓库 `docs/` 目录入口（SELF） |
| E15 | link | 原仓库地址 MoyuScript（已删除说明） | UPSTREAM_LABELED | 保留并明确"上游原仓库" |
| E16 | link | "Github 仓库"行 → nemo2011 | SELF | 改为本仓库地址；nemo2011 归入沿革段 |
| E17 | section | 沿革说明（MoyuScript 2020 创建 → 2022 停维护 → 本仓库 fork + 首末 commit 链接） | UPSTREAM_LABELED | 保留，衔接注记构成三级来源链 |
| E18 | section | 简介（Python 库、覆盖范围） | SELF | 保留，事实核对 |
| E19 | section | 特色列表（覆盖广、代理、BV/AV、异步、三客户端、反爬） | SELF | 保留，与 AGENTS.md 概览核对 |
| E20 | section | 安装段：`pip3 install bilibili-api-python` / `-dev` / 上游 git@dev | SELF | 改为本仓库 git 安装 + Release 资产安装（R2） |
| E21 | section | 请求库自装说明（aiohttp/httpx/curl_cffi） | SELF | 保留 |
| E22 | code-sample | 视频信息示例（`video.Video(bvid=...)` + `get_info()`） | SELF | 保留，与现行 API 签名核对 |
| E23 | code-sample | 点赞示例（`Credential(sessdata=…)` + `like(True)`） | SELF | 保留，占位符变量注明；与现行签名核对 |
| E24 | callout | 凭据泄露 Warning | SELF | 保留（凭据安全对齐 FR-008） |
| E25 | section | 异步迁移段（含上游 sync-executor 链接） | UPSTREAM_LABELED | 保留正文，链接标注上游 |
| E26 | section | 请求库选择（`select_client` / `impersonate`） | SELF | 保留，与现行 API 核对 |
| E27 | section | FAQ：指名传参 / 412 与代理 / 自定义请求库（上游链接）/ 缺功能提 Issue | SELF / UPSTREAM_LABELED | 逐条：自定义请求库链接标注上游；Issue 指向本仓库 |
| E28 | section | FAQ：贡献指南（clone 上游、develop 分支、上游 CONTRIBUTING.md） | SELF | 改写为本 fork 工作流（uv、PR→dev；不深链已漂移的 CONTRIBUTING.md，R7） |
| E29 | section | FAQ：稳定性说明（Issues 链接） | SELF | Issues 改指本仓库 |
| E30 | footnote | [^1]–[^5] 代码来源致谢（AV/BV 算法、danmaku2ass、cookie 刷新、bilibili-API-collect） | UPSTREAM_LABELED | 保留（来源致谢义务） |
| E31 | linkdefs | 引用定义块（docs / api.json / license / stargazers / issues-new / get-credential / pypi / pypi-dev） | 混合 | stargazers、pypi、pypi-dev REMOVED；issues-new 改 SELF；docs 系标注上游；api.json/license 改 SELF |
| E32 | section | Star History 图（上游仓库） | REMOVED | —（上游数据失真，R5） |

## 状态迁移

无运行时状态机。清单本身的生命周期：**登记（实现前补登记遗漏元素）→ 处置（按 disposition 改造）→ 清点验收（SC-002 逐条核销）**；验收后发现的新引用回流到"登记"步骤。
