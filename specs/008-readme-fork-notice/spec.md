# Feature Specification: README 适配本 Fork 仓库并声明上游来源与 AI 维护

**Feature Branch**: `008-readme-fork-notice`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "修改 README.md, 使其适配当前的项目并加上, 注: '本项目Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支并由AI维护'"

**背景**: 当前 `README.md` 基本原样继承了上游 `nemo2011/bilibili-api` 的内容：徽章、安装指引、仓库链接、贡献指南、Star History 等全部指向上游仓库与上游的 PyPI 发布渠道。本项目是独立维护的 fork（仓库为 `LaowuClaw/bilibili-api-python`），分发方式（GitHub Release 挂构建资产、不上 PyPI）、开发工作流（uv 管理、lint 门禁、测试分层）、维护方式（AI 维护）均与上游不同，读者按现 README 操作会被误导。需在保留 GPL-3.0 许可证声明与上游致谢的前提下，将 README 的归属、安装、开发指引适配为本项目实态，并按用户要求逐字加入 fork 来源与 AI 维护注记。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 访客一眼识别项目来源与维护方式 (Priority: P1)

任何打开本仓库首页或 README 的访客（GitHub 访客、 downstream 使用者、上游社区成员），在不滚动或少滚动的首屏区域内即可读到一条显著的注记，明确说明：本项目 Fork 自 `https://github.com/nemo2011/bilibili-api` 的 commit SHA 为 `027563d2fe7604967242986aac51d693c905` 的分支，并由 AI 维护。注记文字使用用户提供的原文，逐字保留（含 SHA 字符串原样）。

**Why this priority**: 这是用户显式提出的核心诉求，也是 fork 项目的署名义务（GPL-3.0 衍生作品须标明来源）。读者据此立即知道：代码源头在哪、精确到哪个 commit、由谁维护——这决定了他们是否信任、如何反馈、如何对照上游。

**Independent Test**: 对修改后的 README 做字符串精确比对，断言注记原文完整出现一次及以上，且位于首屏区域（标题/徽章区之后的显著位置）。

**Acceptance Scenarios**:

1. **Given** 修改后的 README，**When** 以用户提供的注记原文做精确字符串搜索，**Then** 至少命中一处，且无字符级改写（空格、标点、SHA 均与原文一致）。
2. **Given** 注记所在的 README 首屏区域，**When** 访客阅读，**Then** 无需进入其他文件即可同时获知 fork 来源仓库、来源 commit SHA、AI 维护三个事实。
3. **Given** 注记中的上游 commit SHA，**When** 访客将其用于上游仓库定位，**Then** SHA 字符串与用户提供的原文逐字一致，未被截断、补全或改写。

---

### User Story 2 - 新用户按 README 快速上手成功 (Priority: P2)

初次接触本项目的使用者按 README 的安装指引，在一台干净的 Python ≥ 3.10 环境中完成安装，并跑通 README 给出的首个示例（获取视频信息）。安装指引与本项目的实际分发方式一致：不以上游 PyPI 包（`bilibili-api-python` / `bilibili-api-dev`）作为本项目的安装入口，而是引导从本仓库安装（git 安装 / GitHub Release 构建资产）。异步请求库自行的安装说明与示例代码保持可运行。

**Why this priority**: README 的首要职能是让新用户用起来。现 README 的 `pip3 install bilibili-api-python` 指向的是上游发布的包而非本 fork 的代码，用户装到的不是本项目——这是事实性错误，必须修正，否则快速上手路径整体失效。

**Independent Test**: 在干净环境中按 README 安装指引逐步执行，随后原样运行 README 中的首个示例代码，断言安装成功且示例输出视频信息。

**Acceptance Scenarios**:

1. **Given** 干净的 Python ≥ 3.10 环境，**When** 按 README 安装指引执行，**Then** 安装的是本仓库的代码（来源为本仓库 git 地址或本项目 GitHub Release 资产），而非上游 PyPI 包。
2. **Given** 安装完成的环境，**When** 运行 README 中的视频信息示例，**Then** 示例正常输出，无需修改代码。
3. **Given** README 中所有安装命令与版本徽章，**When** 逐一核对指向，**Then** 不存在把上游 PyPI 包表述为本项目安装方式的条目。

---

### User Story 3 - 开发者按 README 进入本项目工作流 (Priority: P3)

想给本仓库贡献代码或参与维护的开发者，按 README 的开发/贡献指引可以一次性完成：环境搭建（uv 管理）、本地检查（lint 门禁脚本）、测试运行（分层测试的常用命令入口）、提交规范（Conventional Commits）与 PR 目标分支（`dev`）。指引与项目实际工作流一致，不再指向上游仓库的 CONTRIBUTING 指南与上游分支模型。

**Why this priority**: 完整工作流细节已有 AGENTS.md / 宪章承载，README 只需给对入口与方向；但若残留上游贡献指引，开发者会向上游仓库发 PR，造成误导，故仍须修正。

**Independent Test**: 按 README 开发指引在本地新克隆的仓库执行环境搭建与检查命令，断言命令序列可原样跑通至门禁全绿。

**Acceptance Scenarios**:

1. **Given** 本地新克隆的本仓库，**When** 按 README 开发指引执行环境搭建命令，**Then** 环境就绪，命令均为本项目实际可用的命令。
2. **Given** 已就绪的开发环境，**When** 按 README 给出的检查/测试命令入口执行，**Then** 命令真实存在于本项目且可直接运行。
3. **Given** README 的贡献说明，**When** 开发者准备提交 PR，**Then** 说明指向本仓库的 `dev` 分支，且提交规范描述与项目 Git Hook 校验规则一致。

---

### Edge Cases

- **上游继承元素的去留**：徽章（CI / Stars / 版本）、Star History 图、文档站链接均继承自上游。处理原则：凡反映上游仓库状态、对本项目失真的元素（Stars 数、上游 CI 状态、上游 PyPI 版本）默认移除或改为指向本项目；本项目未部署独立文档站，上游文档站链接可保留但必须明确标注为"上游文档"。
- **注记 SHA 字符串长度异常**：用户提供的 commit SHA（`027563d2fe7604967242986aac51d693c905`）非标准 40 位长度。默认逐字使用原文，不截断、不补全、不改写；如后续用户提供修正 SHA，以替换原文处理。
- **上游历史致谢与原仓库说明**：现 README 中"MoyuScript 原仓库（已删除）→ nemo2011 fork"的沿革说明与感谢内容属于 GPL-3.0 衍生作品的来源声明，默认保留，并与本 fork 注记共同构成完整来源链（MoyuScript → nemo2011 → 本项目）。
- **示例中的凭据占位**：README 示例代码与说明中只允许出现占位符（如 SESSDATA 变量名），不得出现任何真实凭据值。
- **README 以外的文档**：`docs/` 下文档由工具链从源码生成，本特性不改动；README 与 docs 站内容的差异（如 README 简述 vs docs 详述）以各自分工处理，不追求一致。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: README MUST 在首屏显著位置逐字包含用户提供的注记："本项目Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支并由AI维护"（引号内内容逐字保留，含标点与 SHA 原文）。
- **FR-002**: README 中每一处仓库归属引用（徽章、链接、Star History、贡献指引、文档链接、脚注引用）MUST 满足以下三态之一：指向本项目实际仓库地址；明确标注为上游（nemo2011 或 MoyuScript）资源并保留；移除。MUST NOT 保留未标注的上游归属引用。
- **FR-003**: 安装指引 MUST 与本项目实际分发方式一致（本仓库 git 安装与 GitHub Release 构建资产），MUST NOT 将上游 PyPI 包（`bilibili-api-python` / `bilibili-api-dev`）表述为本项目的安装方式。
- **FR-004**: 简介与特色描述 MUST 与本项目实际能力一致：Python 异步库、400+ API、`aiohttp` / `httpx` / `curl_cffi` 多客户端、Python ≥ 3.10、反爬支持；不得保留与本项目不符的能力表述。
- **FR-005**: 开发/贡献指引 MUST 反映本项目实际工作流：uv 管理环境、lint 门禁脚本入口、分层测试的常用命令、Conventional Commits 提交规范、PR 目标分支 `dev`。
- **FR-006**: README MUST 保留 GPL-3.0-or-later 许可证声明与使用注意事项（仅限学习与测试、禁止滥用条款），并保留上游来源链说明（MoyuScript 原仓库 → nemo2011 fork → 本 fork）。
- **FR-007**: README 中所有保留的链接 MUST 指向有效目的地；标注为上游的链接 MUST 使读者明确知道离开本项目后到达的是上游资源。
- **FR-008**: README MUST NOT 包含任何真实凭据（SESSDATA、bili_jct 等）或其他敏感信息。

### Key Entities

本特性为文档内容改造，不引入运行时数据实体，略。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 以用户提供的注记原文对 README 做精确字符串比对，100% 逐字命中，且注记位于首屏显著位置（无需滚动或极少滚动即可见）。
- **SC-002**: 对 README 全文的仓库归属引用逐条清点，100% 归入"本项目 / 明确标注的上游 / 已移除"三态之一，0 条未标注的上游归属引用残留。
- **SC-003**: 按 README 安装指引在干净的 Python ≥ 3.10 环境中完成安装并原样跑通首个视频信息示例，全程无需读者自行纠错。
- **SC-004**: 按 README 开发指引在新克隆的本仓库上完成环境搭建并执行到检查入口，指引中的每条命令均可原样执行成功。

## Assumptions

- 本 fork 不在 PyPI 发布（现有版本均以 GitHub Release 挂构建资产分发），故移除上游 PyPI stable / pre-release 徽章与 pip 安装主入口；将来若上 PyPI，再据实更新。
- 本项目未部署独立文档站，"开发文档"链接保留上游文档站地址并明确标注"上游文档"；本项目自身文档以仓库 `docs/` 目录为准。
- 注记使用用户提供的原文逐字嵌入，SHA 字符串长度异常一事按原文处理（见 Edge Cases）。
- Star History 图反映的是上游仓库数据且本项目暂无可观星数，默认移除；徽章中反映上游仓库状态的（Stars、上游 CI、PyPI 版本）默认移除或替换为本项目对应物（如 GitHub Release 版本徽章）。
- README 保持中文为主的行文风格，维持单文件形态，不拆分多文件。
- 上游 logo 图沿用（fork 关系下沿用视觉标识是常规做法），如需替换由后续特性处理。
