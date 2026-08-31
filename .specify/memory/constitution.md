<!--
Sync Impact Report
==================
- Version change: (未批准的模板占位) → 1.0.0（首次批准）
- Modified principles: 无（此前文件为未填充模板，本次为初始填充）
- Added sections:
  - Core Principles（I. 异步优先 / II. 声明式 API 定义 / III. 质量门禁 /
    IV. 分层测试 / V. 兼容性与破坏性变更控制，全部新增）
  - 技术与安全约束（新增）
  - 开发工作流（新增）
  - Governance（新增）
- Removed sections: 无
- Follow-up TODOs: 无（无故意保留的占位符）
- 生成依据：应用户要求，根据项目内容（AGENTS.md、README.md、
  scripts/lint.py 门禁链路、tests/conftest.py 测试分层）自动生成。
-->

# bilibili-api-python Constitution

## Core Principles

### I. 异步优先（Async-First Library）

本项目是纯异步 Python 库，不是 CLI 应用或服务。

- 所有 API 调用函数 MUST 为 `async def`；同步包装仅允许通过
  `utils/sync.py` 的 `@sync` 装饰器提供。
- 库代码中 MUST NOT 出现 `asyncio.run()`——事件循环由调用方负责启动。
- 异步路径中 MUST NOT 使用同步阻塞操作（`time.sleep`、`requests.get` 等）。
- HTTP 访问 MUST 经由 `BiliAPIClient` 抽象层，客户端实现按
  `curl_cffi > aiohttp > httpx` 优先级自动选择；MUST NOT 绕过抽象层
  直接依赖具体客户端。

Rationale：统一的事件模型与客户端抽象是多客户端支持和下游易用性的根基。

### II. 声明式 API 定义（Declarative API Definitions）

API 元信息（URL、HTTP 方法、参数、是否需要登录）MUST 集中声明在
`bilibili_api/data/api/*.json` 中，运行时经 `get_api()` 加载。

- 新增 API 的流程 MUST 为：先在对应 JSON 添加条目，再在对应模块编写
  异步方法调用它。
- 请求 MUST 走 `Api(**api).update_params(**params).result` 统一链路，
  以自动注入 Wbi 签名、buvid、bili_ticket 等反爬参数。
- 调用 API 函数 MUST 使用关键字参数，MUST NOT 使用位置参数。
- 登录态 MUST 由 `Credential` 类封装传递，MUST NOT 在库代码中硬编码凭据。

Rationale：声明式定义让 400+ 接口可审计、可批量维护；统一链路保证
反爬参数注入不遗漏。

### III. 质量门禁（NON-NEGOTIABLE）

`uv run python scripts/lint.py` 是合入前的强制门禁，MUST 全绿通过。

- 门禁链路：`ruff check` → `ruff format --check` → tests/scripts 阻断检查
  → `pyrefly check` → 类型豁免存量棘轮（`scripts/type_ratchet.py`）→
  文档漂移校验。
- pyrefly 豁免错误码基线 MUST 只减不增；某错误码基线清零后 MUST 同步
  从 `pyproject.toml` 的 `[tool.pyrefly.errors]` 豁免表移除该条目。
- 新增或修改公共函数 MUST 提供完整中文 docstring（Args / Returns /
  Raises）并附全面类型注解；随后 MUST 重新运行 `scripts/doc_gen.py`
  生成文档。
- `docs/` 下的 API 文档 MUST NOT 手工编辑。
- MUST NOT 忽略 ruff 报错或跳过门禁脚本。

Rationale：文档与类型由工具链从源码单一事实源生成，任何手工漂移都会
被门禁阻断。

### IV. 分层测试（Test Layering）

测试按对网络与凭据的依赖分为三层，各层边界 MUST 严格遵守：

- 离线用例（`tests/test_offline_*.py`）：MUST NOT 触发网络请求、使用
  真实凭据或执行任何改变账号状态的操作。
- 只读集成用例（`readonly` 标记）：仅允许 GET 式读请求与反爬参数获取，
  MUST NOT 包含写操作；缺凭据时自动降级为警告而不阻塞。
- 写操作集成用例：MUST 经 `tests/conftest.py` 的 `credential` fixture
  获取登录态；凭据 MUST NOT 硬编码或提交（`.bilibili.cookie` 已加入
  `.gitignore`，严禁入库）。
- 集成测试 MUST 控制请求频率（限速 fixture / `BILI_RATELIMIT`），
  避免触发 412 风控。

Rationale：分层让无凭据环境也能获得可信的快速反馈，同时保护测试账号
不被风控。

### V. 兼容性与破坏性变更控制（Compatibility & Breaking Changes）

- 代码 MUST 兼容 CPython 3.10，MUST NOT 使用更高版本独有的语言特性。
- 新增参数 SHOULD 提供默认值以避免破坏性变更；无法避免的破坏性变更
  MUST 在 commit message 中以 `BREAKING CHANGE` footer 标注。
- 错误处理 MUST 使用 `bilibili_api/exceptions/` 自定义异常体系，
  MUST NOT 直接 `raise Exception`。
- 一个提交只做一件事：修 bug 与加功能 MUST 拆分为两个提交。

Rationale：作为被下游广泛依赖的库，接口稳定性即是契约。

## 技术与安全约束

- **语言与运行时**：Python ≥ 3.10；依赖与环境统一由 uv 管理
  （`uv sync` / `uv add`），MUST NOT 用 `pip install` 直接装包。
- **许可证与用途**：GPL-3.0-or-later；本库仅用于学习与测试，MUST NOT
  用于非法用途或滥用行为（恶意刷屏、辱骂黄暴等社区破坏行为）。
- **凭据安全**：SESSDATA、bili_jct 等凭据 MUST NOT 出现在任何提交内容
  或日志输出中。
- **反爬集中管理**：Wbi 签名、buvid、bili_ticket 逻辑集中在
  `utils/_api.py` 与 `utils/_anti_spider.py`；反爬失效时 MUST 优先在该层
  排查修复，MUST NOT 在业务模块散落补丁。
- **解析与临时文件安全**：解析不受信数据（如弹幕 XML）MUST 使用
  `defusedxml` 等安全解析器；临时文件 MUST 使用 `tempfile` 生成且
  外部输入的后缀 MUST 经白名单过滤。
- **调试规范**：MUST NOT 用 `print()` 调试，统一使用 `logging`。

## 开发工作流

1. 功能开发 SHOULD 从 `dev` 分支切出新分支，PR 合入目标为 `dev`；
   维护者在本地 `main` 上的维护性直提交（chore / fix 等，见既有 git
   实践）不视为违规，但 SHOULD 保持"一个提交只做一件事"的粒度。
2. 完成后运行 `uv run python scripts/lint.py` 全量门禁。
3. 新增功能后运行 `uv run python scripts/doc_gen.py` 重新生成文档。
4. 提交信息遵循 Conventional Commits（Git Hook 强制校验），允许的
   type：`build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor`
   `release` `revert` `style` `test` `tests`。
5. 测试命令：无凭据环境 `uv run pytest -m "not integration"`；有凭据
   环境 `uv run pytest`（自动读取 `.bilibili.cookie` 或 `BILI_*`
   环境变量，缺省时集成用例自动 skip）。
6. 需要跟进 b 站接口变更时，参考上游 `bilibili-API-collect` 的最新成果。

## Governance

- 本宪章是项目开发实践的最高准则，与其他文档冲突时以本宪章为准；
  日常开发的运行时指引见 `AGENTS.md`。
- 修订程序：修订 MUST 通过独立提交完成，提交信息以
  `docs: amend constitution to vX.Y.Z ...` 说明变更内容，并在文件头部
  附 Sync Impact Report（版本变化、增删原则、迁移事项）。
- 版本策略遵循语义化版本：原则删除或重新定义为 MAJOR；新增原则或
  章节为 MINOR；措辞与澄清为 PATCH。
- 合规审查：每次 PR review MUST 核对宪章合规性（尤其是质量门禁、
  分层测试与凭据安全三条不可协商红线）；复杂度引入 MUST 在 PR 描述中
  给出理由。

**Version**: 1.0.0 | **Ratified**: 2026-08-31 | **Last Amended**: 2026-08-31
