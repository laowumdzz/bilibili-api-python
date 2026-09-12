# Phase 0 Research: 测试登录凭证流程迁移至独立脚本

**Date**: 2026-09-03 | **Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Technical Context 无 NEEDS CLARIFICATION 项（全部代码为既有实现迁移，无新技术选型）。以下为经代码调研确定的设计决策。

## R1: 模块放置与导入机制

**Decision**: 登录流程 + 缓存校验/刷新 + CLI 入口全部落在 `scripts/login_and_cache.py`；`tests/conftest.py` 与离线测试经 `from scripts.login_and_cache import ...` / `from scripts._login_cache import ...` 导入。

**Rationale**:
- `tests/__init__.py` 存在 ⇒ pytest（默认 import-mode=prepend）将项目根插入 sys.path，这正是今天 `from tests._login_cache import ...` 生效的机制；`scripts/` 无 `__init__.py`，作为命名空间包（PEP 420）在项目根入 sys.path 后可直接导入，无需添加 `__init__.py`、无需任何 sys.path hack。
- 脚本直接运行（`uv run python scripts/login_and_cache.py qrcode`）时模块自身即 `__main__`，其依赖只有 venv 内的 `bilibili_api`（可编辑安装，导入不依赖项目根在 sys.path）与同目录平移模块（见 R2），自包含。
- `bilibili_api/` 库完全不动：登录工具是开发脚本，不属于库公开 API（spec Assumptions），也避免进入 doc_gen / pyrefly 范围。

**Alternatives considered**:
- *放 `bilibili_api/utils/`*：登录工具会随 wheel 发布并进入文档生成范围，违背"库不承载测试工具"的项目边界——否决。
- *conftest 经 `importlib.util.spec_from_file_location` 按路径加载脚本*：绕过包机制、类型与工具链不友好——否决。
- *脚本内 `sys.path.insert` 引导项目根再导入 `tests._login_cache`*：脚本反向依赖 tests 包，语义倒挂——否决。

## R2: 纯缓存逻辑的归宿（保持离线用例纯度）

**Decision**: `tests/_login_cache.py` **原样平移**为 `scripts/_login_cache.py`（不导入 bilibili_api 的纯逻辑模块），`tests/_login_cache.py` 删除；`test_offline_login_cache.py` 仅更新导入行为 `from scripts._login_cache import ...`。

**Rationale**:
- 该离线测试文件头部声明"不导入 bilibili_api"的纯度不变量；若把纯函数并入 `login_and_cache.py`（顶部导入 `login_v2` / `geetest`），导入即拉起 bilibili_api 全链，破坏该不变量。拆成两个模块以最小成本保住它。
- `login_and_cache.py` 顶部 `from scripts._login_cache import ...`（或 re-export 纯函数）统一对外供给；conftest 与脚本共用同一实现，满足 FR-004。
- 内容零改动平移 ⇒ specs/001 契约与既有离线用例语义不变，churn 仅一行导入 + 一次文件移动。

**Alternatives considered**:
- *留在 `tests/_login_cache.py` 不动，脚本反向导入*：脚本依赖 tests 包语义倒挂（同 R1）——否决。
- *合并进 `login_and_cache.py` 单文件*：破坏离线测试纯度不变量——否决。

## R3: 交互 I/O 接缝（notify / prompt 可注入）

**Decision**: 脚本模块的交互输出与输入收敛为可注入的回调接缝：流程函数接受 `notify(message, *, error=False)` 与 `prompt(message) -> str` 两个参数（或等价的轻量 I/O 协议对象），独立运行时缺省为 `print`/`input`（stderr/ stdout 语义与现状对齐），conftest 注入基于 pytest terminal writer 的现有 `_notify` / `_prompt` 包装。

**Rationale**:
- 现有 conftest 的 `_notify` / `_prompt` 专门处理"绕过 pytest 输出捕获 + 终端 writer 回退"这一 pytest 特有语义；迁移后此语义属于 conftest 侧适配，不属于登录流程本身。
- 流程逻辑（二维码轮询、短信+极验、中止判定）与呈现解耦后，两条入口各自映射输出渠道，行为（消息文本、时机、错误标记）保持一致，满足 US2/US3。

**Alternatives considered**:
- *脚本内直接 print，conftest 保留自己的流程副本*：双实现漂移，违背 FR-004/US3——否决。
- *引入 logging 作为唯一通道*：交互式提示（二维码、输入提示）不是日志，混用会破坏终端交互体验；现有 conftest 也未用 logging 呈现交互——否决。

## R4: 缓存校验/刷新的返回形态

**Decision**: 校验/刷新入口返回带状态的富结果（枚举：有效 / 已刷新 / 过期且缺刷新材料 / 网络异常），由调用方各自映射 UX——conftest 侧沿用现状（网络异常 → `pytest.skip` 保留缓存；缺材料 → 删缓存 + `warnings.warn`），脚本独立运行侧输出对应提示。

**Rationale**:
- 现有 `_resolve_cache_usable_fields` 混合了逻辑与 pytest 特有副作用（`pytest.skip`、`warnings.warn`）；把决策点留在调用方，核心逻辑（联网校验、刷新、回写、清理）单点化，行为一致而 UX 各归其位（US3 两个验收场景分别覆盖两入口）。
- 刷新成功回写缓存文件的动作属共享逻辑，保留在脚本模块内。

**Alternatives considered**:
- *抛异常传递状态*：把"过期缺材料"这类正常分支塞进异常流，调用方被迫捕获多种异常类型区分语义——否决。

## R5: CLI 形态、退出码与输出渠道

**Decision**: `uv run python scripts/login_and_cache.py <qrcode|phone>`；无参输出用法提示并以状态码 2 退出（不进入交互，spec 澄清 Q1）；登录成功写缓存后以 0 退出；登录中止/失败以 1 退出（不写缓存）。用户可见输出用 `print`（stderr 用于错误提示），需在 pyproject 为该文件加 `per-file-ignores = ["T201"]`（与 `scripts/lint.py` 等既有命令行脚本同例，并在注释中注明用途）。

**Rationale**:
- argparse `choices` + 位置参数最简地实现"显式指定 + 用法提示 + 退出码 2"，与 `--login` 的取值集合（qrcode/phone）一致。
- T201 豁免逐文件枚举是 pyproject 既有惯例；交互提示非调试输出，不违反宪章"禁止 print 调试"。
- 退出码 0/1/2 区分"成功 / 中止失败 / 用法错误"，便于脚本化调用与验收。

**Alternatives considered**:
- *默认 qrcode / 交互菜单*：spec 澄清已裁定为显式指定——不再考虑。
- *统一 logging*：见 R3——否决。

## R6: isort / 首方包分类

**Decision**: pyproject `[tool.ruff.lint.isort] known-first-party` 增加 `"scripts"`，使 conftest / 测试中 `from scripts... import` 按首方排序，避免 I001。

**Rationale**: `known-first-party = ["src", "tests"]` 为显式枚举制，新增 `scripts.` 导入后不加入即被归入第三方段导致排序报错；一行配置即可。

## R7: 门禁与文档生成影响面

**Decision**: 预期影响面：`ruff check ./tests/ ./scripts/`（新代码须全绿）、`ruff format --check ./bilibili_api/`（不受影响）、pyrefly（不受影响，范围仅 `bilibili_api/`）、type_ratchet（基线不变）、doc_gen / docs/modules/（不受影响，scripts 不在生成范围）。

**Rationale**: 逐项核对 `scripts/lint.py` 门禁链路得出；本特性不新增库公开符号 ⇒ 文档漂移校验无输入变化。

## R8: 兼容性基线（行为对照来源）

**Decision**: 以迁移前 `tests/conftest.py` 的可观察行为为验收基线：`--login` 成功写缓存并提示路径、中止四类原因（用户中断 / 连续超时 / 流程失败 / EOF）的提示语义与回退链、缓存 absent / corrupt / 网络异常三分支处理、`credential` fixture 优先级合并——全部保持不变。

**Rationale**: spec FR-003 / US2 / SC-002 的"行为兼容"需可对照的基线；迁移属等价重构 + 新增独立入口，唯一新增行为是 CLI（FR-001/FR-002）。
