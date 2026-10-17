<!--
Sync Impact Report
==================
- Version change: 1.0.2 → 1.1.0（MINOR：原则内容实质性扩展，无删除或放宽）
- Modified principles:
  - II. 声明式 API 定义：确立 `bilibili-api-registry/` 为接口信息主要来源，
    补充"先查 registry → 脚本增量同步 → 再写模块方法"的标准次序与
    纯增量同步约束；接口规模口径由"400+"更正为"当前 800+（以 data/api
    实际条目为准）"。
  - IV. 分层测试：由三层（离线 / 只读 / 写操作）扩展为四级凭据分层
    （cred0–cred3），纳入特性 007 已落地的层预算、六态零残留、账号安全
    五类判定、限速与风控中止规则；原三层边界保持不变。
- Added sections: 无
- Removed sections: 无
- 迁移事项: 无（新规则与当前代码、测试及 CI 实践一致，不要求存量改造）
- Follow-up TODOs: 无
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
  `aiohttp > httpx` 优先级自动选择；MUST NOT 绕过抽象层
  直接依赖具体客户端。

Rationale：统一的事件模型与客户端抽象是多客户端支持和下游易用性的根基。

### II. 声明式 API 定义（Declarative API Definitions）

API 元信息（URL、HTTP 方法、参数、是否需要登录）MUST 集中声明在
`bilibili_api/data/api/*.json` 中，运行时经 `get_api()` 加载。

- 接口信息的主要来源 MUST 是项目根目录下的 `bilibili-api-registry/`
  （独立嵌套 git 仓库，抽取自 bilibili-API-collect 文档）；该目录
  MUST NOT 作为子模块或普通目录纳入本仓库追踪。
- 新增 API 的标准次序 MUST 为：先查 registry 对应条目的 URL / method /
  params / 鉴权说明；运行 `scripts/sync_api_registry.py`（先 `--dry-run`
  预览）纯增量同步缺失条目；再在对应模块编写异步方法调用。
- 仅当 registry 未覆盖该接口时，才允许手工编辑 `data/api/*.json`，且
  SHOULD 优先补齐 registry 后再同步。
- 同步 MUST 保持纯增量：已存在接口一律不动；gRPC（本项目无运行时支持）
  与 `method=OTHER` 条目 MUST 跳过；registry 的 `doc_source` / `notes`
  等元数据 MUST NOT 进入 JSON（`Api(**api)` 不接受未知键）。
- 请求 MUST 走 `Api(**api).update_params(**params).result` 统一链路，
  以自动注入 Wbi 签名、buvid、bili_ticket 等反爬参数。
- 调用 API 函数 MUST 使用关键字参数，MUST NOT 使用位置参数。
- 登录态 MUST 由 `Credential` 类封装传递，MUST NOT 在库代码中硬编码凭据。

Rationale：registry 以可回溯的 `doc_source` 提供接口单一事实源，纯增量
同步让当前 800+ 接口可审计、可批量维护；统一调用链路保证反爬参数注入
不遗漏。（接口数量以 `data/api/*.json` 实际条目为准。）

### III. 质量门禁（NON-NEGOTIABLE）

`uv run python scripts/lint.py` 是合入前的强制门禁，MUST 全绿通过。

- 门禁链路：`ruff check` → `ruff format --check` → tests/scripts 阻断检查
  → `pyrefly check` → 类型零容忍棘轮校验（`scripts/type_ratchet.py`）→
  文档漂移校验。
- 类型豁免机制已于 2026-09 特性 005（specs/005-pyrefly-type-debt）
  整体退役：`pyproject.toml` 不再配置 `[tool.pyrefly.errors]` 豁免表，
  `scripts/type_ratchet.py` 基线为空表，类型检查默认全量启用、零容忍。
- MUST NOT 重新引入类型豁免：不得恢复豁免表条目，不得将棘轮基线从零
  上调；任何新增类型错误 MUST 就地修复而非豁免。
- 新增或修改公共函数 MUST 提供完整中文 docstring（Args / Returns /
  Raises）并附全面类型注解；随后 MUST 重新运行 `scripts/doc_gen.py`
  生成文档。
- `docs/` 下的 API 文档 MUST NOT 手工编辑。
- MUST NOT 忽略 ruff 报错或跳过门禁脚本。

Rationale：文档与类型由工具链从源码单一事实源生成，任何手工漂移都会
被门禁阻断。

### IV. 分层测试（Test Layering）

全部测试 MUST 统一由 pytest 运行；测试按对网络、凭据与账号状态的依赖
分层，各层边界 MUST 严格遵守。

- 离线用例（`tests/test_offline_*.py`）：MUST NOT 触发网络请求、使用
  真实凭据或执行任何改变账号状态的操作。
- 只读集成用例（`readonly` 标记）：仅允许 GET 式读请求与反爬参数获取，
  MUST NOT 包含写操作；缺凭据时自动降级为警告而不阻塞。该标记可与
  cred0 / cred1 并存。
- 需凭据用例 MUST 恰好声明一个等级标记（cred0–cred3 之一）；漏标或
  错标由 `tests/conftest.py` 收集期防护发现，`BILI_STRICT_TIERS=1`
  时 MUST 升级为收集错误。
  - `cred0` 核心冒烟：只读、接口稳定；整层 ≤ 30 请求；单账号验收
    MUST 全绿。
  - `cred1` 核心读回归：只读核心读路径；cred0 + cred1 合计 ≤ 400 请求。
  - `cred2` 自清理写生命周期：仅限可逆写（存在配对恢复 API 且恢复有
    断言）与"自身状态类"白名单操作；会话结束 MUST 六态零残留
    （关注 / 收藏 / 点赞 / 评论 / 弹幕 / 稍后再看）。
  - `cred3` 高危显式门控：资源消耗类、无清理可能的公开发布类、
    破坏性类、账号身份特定类；默认收集期即排除，MUST NOT 在常规验收
    与 CI 中执行，仅显式 `-m cred3` 运行。
- 账号安全判定 MUST 遵循五类操作判定表（可逆写 / 自身状态类 /
  资源消耗类 / 公开发布类 / 破坏性及身份特定类）；权威映射见
  `specs/007-credential-test-tiers/data-model.md`。无法对号入座或未完成
  举证的操作 MUST 从严归入 cred3。
- cred2 的公开发布类写操作 MUST 以账号自有内容为对象，运行时动态解析
  （`get_self_info` → `User(mid).get_videos()`），MUST NOT 硬编码他人
  mid / aid；"自身状态类"白名单为封闭枚举，新增成员 MUST 逐条给出
  仅自身可见证据、六态清单对照与无对外发布形态核查。
- 集成用例 MUST 经 `tests/conftest.py` 的 `credential` fixture 获取登录态；
  凭据 MUST NOT 硬编码或提交（`.bilibili.cookie` 已加入 `.gitignore`，
  严禁入库）。
- 集成用例 MUST 控制请求频率：`BILI_RATELIMIT` 缺省 1.5 秒，循环遍历型
  用例 MUST 在循环体内额外节流；`BILI_COUNT_REQUESTS=1` 时以服务端视角
  计数，层预算以该读数为准；`BILI_ABORT_ON_RISK=1` 时首个 412 类风控
  响应 MUST 中止整个会话。

Rationale：分层让无凭据环境也能获得可信的快速反馈，同时以最小请求预算
与自清理约束保护共享测试账号，避免触发 412 风控或留下账号残留。

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
   `dev` 远端建立前，外部贡献 MUST 先通过 Issue 与维护者沟通。维护者
   在本地 `main` 上的维护性直提交（chore / fix 等，见既有 git 实践）
   不视为违规，但 SHOULD 保持"一个提交只做一件事"的粒度。
2. 完成后运行 `uv run python scripts/lint.py` 全量门禁。
3. 新增功能后运行 `uv run python scripts/doc_gen.py` 重新生成文档。
4. 提交信息遵循 Conventional Commits（Git Hook 强制校验），允许的
   type：`build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor`
   `release` `revert` `style` `test` `tests`。
5. 测试命令：离线 `uv run pytest -m "not integration"`；常规验证
   `uv run pytest`（cred3 收集期自动排除）；核心冒烟
   `uv run pytest -m cred0`；读回归 `uv run pytest -m "cred0 or cred1"`；
   高危层仅在显式需要时 `uv run pytest -m cred3`。CI 集成任务使用
   `uv run pytest -m "cred0 or cred1 or cred2"`。
6. 跟进 b 站接口变更时，MUST 以 `bilibili-api-registry/` 为主要来源：
   先查条目 `doc_source` 回溯源文档，批量补齐运行
   `uv run python scripts/sync_api_registry.py`。
7. 新增或调整需凭据用例时，MUST 同步更新
   `specs/007-credential-test-tiers/data-model.md` 的层级映射与预算表
   （涉及"自身状态类"白名单时按 IV 项证据义务执行）。

## Governance

- 本宪章是项目开发实践的最高准则，与其他文档冲突时以本宪章为准；
  日常开发的运行时指引见 `AGENTS.md`。
- 凭据测试分层的权威映射表为
  `specs/007-credential-test-tiers/data-model.md`；宪章、`AGENTS.md` 与
  测试 marker 的层级描述 MUST 与该表保持一致。
- 修订程序：修订 MUST 通过独立提交完成，提交信息以
  `docs: amend constitution to vX.Y.Z ...` 说明变更内容，并在文件头部
  附 Sync Impact Report（版本变化、增删原则、迁移事项）。
- 版本策略遵循语义化版本：原则删除或重新定义为 MAJOR；新增原则或
  章节为 MINOR；措辞与澄清为 PATCH。
- 合规审查：每次 PR review MUST 核对宪章合规性（尤其是质量门禁、
  分层测试与凭据安全三条不可协商红线）；复杂度引入 MUST 在 PR 描述中
  给出理由。

**Version**: 1.1.0 | **Ratified**: 2026-08-31 | **Last Amended**: 2026-10-17
