# AGENTS.md — bilibili-api-python

> AI 编码助手常驻工作指南。这里只保留每次会话都需要、且无法从仓库直接推断的规则；可延后内容按“权威文档”链接按需加载。项目治理最高准则为 `.specify/memory/constitution.md`，冲突时以宪章为准。

## 项目概要

`bilibili-api-python` 是封装 B 站（bilibili.com）各类 API 的 Python 异步库，覆盖视频、直播、用户、动态、专栏、番剧、音频、漫画等；全部接口异步，请求客户端支持 aiohttp（运行时硬依赖）与 httpx（可选）。

- **语言**：Python ≥ 3.10，代码须兼容 CPython 3.10，不得使用更高版本独有特性。
- **许可**：GPL-3.0-or-later。
- **版本**：见 `bilibili_api/__init__.py` 的 `BILIBILI_API_VERSION`。
- **远端**：https://github.com/laowumdzz/bilibili-api-python（fork 自 nemo2011/bilibili-api，由 AI 维护）。
- **贡献路径**：PR 目标分支为 `dev`（远端尚未建立；建立前外部贡献先通过 Issue 沟通）。本地维护性提交直接在 `main` 进行，推送远端仅在用户明确要求时执行。
- **接口事实来源**：`bilibili-api-registry/`（项目根目录下的独立嵌套 git 仓库，未纳入本仓库追踪，抽取自 bilibili-API-collect 文档；获取步骤见「接口来源与新增 API 流程」）。
- **Python 环境**：uv 管理的 `.venv`；所有命令使用 `uv run` 前缀。

## 权威文档（按需加载）

| 文档 | 用途 |
|------|------|
| `.specify/memory/constitution.md` | 项目宪章，最高准则 |
| `specs/007-credential-test-tiers/data-model.md` | 凭据测试层级映射与账号安全判据（canonical owner） |
| `specs/007-credential-test-tiers/contracts/test-tier-selection.md` | 测试命令矩阵、限速 / 计数 / 中止契约 |
| `specs/007-credential-test-tiers/quickstart.md` | 分层验收步骤与记录 |
| `specs/001-pytest-temp-login/contracts/cli-option.md`、`specs/003-login-cache-script/data-model.md` | `--login` 与凭据回退链细节 |
| `docs/modules/` | 由 docstring 自动生成的 API 文档（禁止手改） |
| `scripts/sync_api_registry.py` | registry → `bilibili_api/data/api` 同步规则（模块 docstring） |

## 接口来源与新增 API 流程

`bilibili-api-registry/` 是接口信息的主要来源，也是 `bilibili_api/data/api/*.json` 的同步来源。它是项目根目录下的独立嵌套 git 仓库，**不纳入本仓库跟踪**（不是子模块，勿提交），新克隆中默认不存在。

**获取（新克隆 / 新环境）：**

1. 从维护者处获取内部 Git 服务上的 registry 仓库地址与访问权限；已有副本可用 `git -C bilibili-api-registry remote get-url origin` 查看地址。
2. 在项目根目录克隆并固定到已知可用基线提交（2026-08-22，当前 `data/api` 与之同步）：
   ```bash
   git clone <registry-url> bilibili-api-registry
   git -C bilibili-api-registry checkout df7a5f65e29e6b456253e529846059da57a10637
   ```
3. 验证：`bilibili-api-registry/schema.json` 存在，且 `uv run python scripts/sync_api_registry.py --dry-run` 能读出 registry 条目（而非报错）。目录缺失或为空时脚本会以非零状态退出并打印获取指引。

**新增 API 的标准流程：**

1. 先查 registry 对应类别 JSON 的 URL / method / params / 鉴权说明（`doc_source` 可回溯源文档）。
2. `uv run python scripts/sync_api_registry.py --dry-run` 预览，确认后去掉 `--dry-run` 执行纯增量同步。
3. 在对应模块编写异步方法调用。
4. 仅当 registry 未覆盖该接口时，才手工编辑 `data/api/*.json`，并优先补齐 registry。

registry 的 `doc_source` / `notes` 等字段不会进入 `data/api/*.json`；类别映射与完整同步原则见 `scripts/sync_api_registry.py` 模块 docstring。

## 常驻命令

环境与门禁：

```bash
uv sync                                                   # 安装依赖（含 dev 组）
uv run python install.py                                  # 初始化 Git Hooks
uv run python scripts/lint.py                             # 全量门禁
uv run --with "mypy==1.18.2" python scripts/doc_gen.py    # 改 docstring 后重新生成 docs/modules
```

`scripts/lint.py` 依次执行 ruff check / format、tests + scripts 阻断检查、pyrefly 全量类型检查、`scripts/type_ratchet.py` 零容忍校验与 `docs/modules/` 漂移校验（CI 设 `DOCS_DRIFT_STRICT=1`，漂移即失败）。不要跳过门禁。

测试：

```bash
uv run pytest -m "not integration"   # 仅离线，无需凭据
uv run pytest -m cred0               # 核心冒烟（单账号必全绿）
uv run pytest -m "cred0 or cred1"    # 冒烟 + 读回归（合计 ≤ 400 请求）
uv run pytest -m "not cred3"         # 常规验证（与不带 -m 的默认全量同义）
uv run pytest -m readonly            # PR 只读回路
uv run pytest -m cred3               # 高危层，仅在显式需要时使用
```

单模块测试：`uv run pytest tests/test_video.py`。cred3 在收集期被 deselect（不是 skip）：默认运行与不含 `cred3` token 的 `-m` 表达式都不会执行高危用例；只有显式 `-m cred3` 才收集。

CI 口径以 `.github/workflows/ci.yml` 为准：PR 跑 `-m readonly`；每周集成任务跑 `-m "cred0 or cred1 or cred2"`，并强制启用 `BILI_COUNT_REQUESTS=1` / `BILI_ABORT_ON_RISK=1` / `BILI_REQUEST_BUDGET=400`。

## 测试与账号安全边界

测试账号为**单一共享账号**。每个需凭据用例**恰好归属一层**（以显式 marker 声明；漏标 / 错标由 conftest 收集期防护发现，`BILI_STRICT_TIERS=1` 时升级为收集错误）。层级语义：

| 层级 | 判据（全部满足） | 请求预算 | 清理要求 |
|------|------------------|----------|----------|
| `cred0` 核心冒烟 | 只读；接口稳定（不依赖容错码）；登录态 + 反爬链路 + 核心读的 minimal 集合 | 整层 ≤ 30 | 无写，无需清理 |
| `cred1` 核心读回归 | 只读；核心模块主读路径；允许保留既有容错码（-404 / -352 / -403 等） | cred0+cred1 合计 ≤ 400 | 无写，无需清理 |
| `cred2` 自清理写生命周期 | 仅限可逆写（配对恢复 + 断言）与“自身状态类”白名单操作 | 不设独立预算 | 六态零残留（关注 / 收藏 / 点赞 / 评论 / 弹幕 / 稍后再看） |
| `cred3` 高危显式门控 | 资源消耗类 / 无清理可能的公开发布类 / 破坏性类 / 账号身份特定类 | 无（默认永不执行） | 无（不默认执行，无验收义务） |

完整规则与验收流程：`specs/007-credential-test-tiers/data-model.md`（层级 / 账号安全）、`specs/007-credential-test-tiers/contracts/test-tier-selection.md`（命令 / 计数）、`specs/007-credential-test-tiers/quickstart.md`（验收）。

- **写操作边界**：`cred2` 仅允许可逆写（存在配对恢复 API 且恢复结果可断言）与“自身状态类”白名单；公开发布只有在目标为自有内容 **且** 有删除配对时才按可逆写归 `cred2`，否则归 `cred3`；资源消耗、破坏性与账号身份特定操作归 `cred3`，默认永不执行。
- **自有内容**：`cred2` 公开发布类写操作 MUST 以账号自有内容为对象——运行时经 `get_self_info` → `User(mid).get_videos()` 动态解析，**禁止硬编码**他人 mid / aid；解析不到则条件跳过。
- **白名单治理**：“自身状态类”为**封闭枚举**。新增成员须在 `specs/007-credential-test-tiers/data-model.md` 权威映射表条目中逐条给出三条件依据（仅自身可见的证据、六态清单对照、无对外发布形态的核查），由 PR 评审者核验；任一条件事后失效时自动降层至 `cred3` 并同步更新映射表。
- **兜底规则**：无法对号入座或未完成举证的操作，一律从严归 `cred3` 待裁。
- **限速与预算**：`BILI_RATELIMIT` 缺省 **1.5** 秒（显式设置含 0 按设置值生效）；循环遍历型用例在循环体内 `await asyncio.sleep(0.5)`。层预算以 `BILI_COUNT_REQUESTS=1` 的计数器读数为准（cred0 ≤ 30、cred0+cred1 ≤ 400）。`BILI_ABORT_ON_RISK=1` 时首个 412 类响应（HTTP 412 或 -352 等效码）即中止会话；`BILI_REQUEST_BUDGET=<n>` 超限以失败退出。完整计数口径见契约 §5–6。
- **凭据来源**（优先级从高到低）：`--login qrcode|phone` 显式重新登录（成功写系统 TEMP 缓存）> TEMP 缓存 > `BILI_*` 环境变量（`BILI_SESSDATA` / `BILI_CSRF` / `BILI_BUVID3` / `BILI_DEDEUSERID`）> 项目根 `.bilibili.cookie`。全部不可用时集成用例自动 skip。**任何提示、错误、日志都不得输出凭据字段值**；`.bilibili.cookie` 与 TEMP 缓存永不入库。
- **独立登录**：`uv run python scripts/login_and_cache.py qrcode`（扫码）或 `phone`（短信）。
- **离线用例**：只验证纯本地逻辑，禁止网络请求、真实凭据或改变账号状态的操作；放在 `tests/test_offline_*.py`。
- **只读集成**：`readonly` 标记仅允许 GET 式读请求与反爬参数获取，严禁写操作；可与 `cred0` 并存。
- **顺序无关**：用例所需资源在用例或其夹具内创建并在结束时清理（`teardown_retry` fixture）；任意子集（含单用例）独立运行都应通过。
- **已知覆盖缺口**：login_v2 登录链路、视频上传链路暂无集成覆盖（追踪见 `specs/007-credential-test-tiers/spec.md`）。

## 编码规范

- 遵循 PEP 8；提交前 `scripts/lint.py` 必须全绿。
- 类型检查零容忍：pyrefly 存量豁免已整体退役，`pyproject.toml` 的 `[tool.pyrefly.errors]` 豁免表已移除；任何新增类型错误都会被门禁拦截。
- 函数参数与返回值全面类型注解；公共函数使用完整中文 docstring（Args / Returns / Raises），`scripts/doc_gen.py` 会据此生成文档。
- 下划线命名，与现有代码保持一致；中英文之间加半角空格（含 docstring 与注释）。
- 所有 API 调用函数使用 `async def`；库代码禁止 `asyncio.run()`（由调用方负责）。
- 调用 API 使用**关键字参数**；新增参数优先设置默认值，避免破坏性变更。
- 使用项目自定义异常（`bilibili_api/exceptions/`），不要直接 `raise Exception`；常用 `ArgsException`、`ResponseCodeException`、`NetworkException`。
- 控制请求并发，避免触发 412 风控。

## 提交与分支

- 提交信息遵循 Conventional Commits（Git Hook + CI 校验）：`<type>(<scope>)?: <description>`。
- 允许的 type：`build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor` `release` `revert` `style` `test` `tests`。
- 破坏性变更尽量避免；必须时用 `!` 并在 body 写 `BREAKING CHANGE:`。
- 一个提交只做一件事（修 bug + 加功能 = 两个提交）。
- 不要主动 push 到远端；本地维护性提交直接在 `main` 进行。

## 常见陷阱

- **412 Precondition Failed**：请求过快，降低并发或 `request_settings.set_proxy(...)`。
- **Wbi 签名失效**：B 站不定期轮换密钥；大批 API 失效时优先检查 `recalculate_wbi`。
- **Cookies 过期**：用 `Credential.check_refresh()` 检查 / 刷新。
- **请求库缺失**：两者都未安装时 `select_client` 抛 `ArgsException`（提示安装 aiohttp / httpx）。
- **接口变更**：先查 registry 条目的 `doc_source` 回溯源文档，再走同步脚本批量补齐。

## 不要做的事

- 不要直接修改 `docs/modules/` 或 `docs/` 下的 API 文档；改 docstring 后用 `scripts/doc_gen.py` 生成。
- 不要用 `pip install` 直接装包，统一用 `uv add` / `uv sync`。
- 不要在库代码或测试中硬编码凭据；不要把 `.bilibili.cookie` / TEMP 缓存提交到仓库。
- 不要用 `print()` 调试，用 `logging`。
- 不要忽略 ruff / pyrefly 错误，不要跳过 `scripts/lint.py`。
- 不要主动 push 到远端；本地提交直接在 `main`。
- 不要使用位置参数调用 API 函数，统一用关键字参数。
- 不要在异步代码中使用同步阻塞操作（`time.sleep`、`requests.get` 等）。
- 不要在 `cred0` / `cred1` 中引入写操作，或让 `cred3` 进入默认运行 / CI。
- 不要在测试中硬编码他人 mid / aid 作为写目标。
