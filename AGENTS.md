# AGENTS.md — bilibili-api-python

> AI 编码助手工作指南。在此项目下工作时遵循这些规则。

## 项目概要

`bilibili-api-python` 是一个 Python 异步库，封装了 B 站（bilibili.com）的各类 API，涵盖视频、直播、用户、动态、专栏、番剧、音频、漫画等功能。400+ API 接口，全部异步，支持多请求客户端（aiohttp / httpx / curl_cffi）。

- **语言:** Python ≥ 3.10（代码须兼容 CPython 3.10，不得使用更高版本独有特性）
- **许可证:** GPL-3.0-or-later
- **当前版本:** 见 `bilibili_api/__init__.py` 中的 `BILIBILI_API_VERSION`
- **上游仓库:** https://github.com/LaowuClaw/bilibili-api-python
- **PR 目标分支:** `dev`（不是 `main`）
- **Python 环境:** 使用 uv 管理的 `.venv` 虚拟环境，所有命令用 `uv run` 前缀

## 项目结构

```
bilibili_api/            # 库源码
├── __init__.py          # 统一导出所有子模块
├── video.py             # 视频（最大模块，2600+ 行）
├── live.py              # 直播 + 弹幕 WebSocket
├── user.py              # 用户
├── dynamic.py           # 动态
├── article.py           # 专栏
├── bangumi.py           # 番剧
├── login_v2.py          # 登录（密码/二维码/短信）
├── video_uploader.py    # 视频上传
├── interactive_video.py # 互动视频
├── session.py           # 私信
├── comment.py           # 评论
├── search.py            # 搜索
├── ...                  # 其他功能模块
├── utils/
│   ├── network.py       # 网络层兼容 re-export（Credential / Api / request_settings）
│   ├── _api.py          # API 请求核心（反爬逻辑入口：recalculate_wbi / get_buvid / get_bili_ticket）
│   ├── _anti_spider.py  # 反爬虫主体实现与参数缓存（AntiSpiderCache）
│   ├── utils.py         # get_api() / 工具函数
│   ├── sync.py          # 同步包装器 (@sync)
│   ├── AsyncEvent.py    # 事件系统基类
│   ├── danmaku.py       # 弹幕数据结构
│   ├── danmaku2ass.py   # 弹幕转 ASS 字幕
│   ├── picture.py       # Picture 类
│   ├── parse_link.py    # 链接解析
│   └── ...
├── exceptions/          # 异常体系（每个异常一个文件）
├── clients/             # 请求客户端适配
│   ├── AioHTTPClient.py
│   ├── HTTPXClient.py
│   └── CurlCFFIClient.py
├── data/
│   ├── api/             # API 定义 JSON（URL / method / params / verify）
│   └── *.json           # 静态数据（分区、语言、标签等）
└── tools/               # 附带工具（ivitools / parser）
scripts/                 # 开发脚本
├── doc_gen.py           # 文档自动生成（从 docstring）
├── lint.py              # ruff check + format + pyrefly 类型检查 + 豁免错误码存量棘轮（type_ratchet）
├── type_ratchet.py      # pyrefly 豁免错误码存量棘轮校验（基线只减不增）
└── get_*.py             # 数据抓取脚本
tests/                   # 测试套件（统一由 pytest 运行）
├── conftest.py          # 共享 fixtures（credential / 限速 / integration 标记）
├── test_offline_*.py    # 离线单元/冒烟测试（无需凭据与网络）
└── test_*.py            # 各模块集成测试（需要 BILI_* 凭据，缺凭据自动 skip）
docs/                    # docsify 文档站
.githooks/               # commit-msg + pre-commit 钩子
```

## 核心架构模式

### 1. API 定义与调用

API 元信息存储在 `bilibili_api/data/api/*.json` 中，定义了 URL、HTTP 方法、参数和是否需要登录验证。运行时通过 `get_api("field")` 加载。

调用链路：`get_api()` 加载 JSON → `Api(**api).update_params(**params).result` 发起请求 → 自动注入 Wbi 签名、buvid、bili_ticket 等反爬参数 → 返回解析后的 JSON。

**新增 API 时：** 在对应的 `data/api/*.json` 中添加条目，然后在对应模块的 Python 文件中编写异步方法调用它。

### 2. Credential 凭据体系

`Credential` 类（`utils/network.py`）封装登录态：`sessdata`、`bili_jct`、`buvid3`、`buvid4`、`dedeuserid`、`ac_time_value`。大部分写操作需要 Credential。通过 `credential.get_cached_cookies()` 获取完整 Cookies。

### 3. 请求客户端抽象

`BiliAPIClient`（ABC）定义了 HTTP 请求、WebSocket、文件下载的统一接口。三种实现按优先级自动选择：`curl_cffi` > `aiohttp` > `httpx`。可通过 `select_client()` 切换，也可 `register_client()` 注册自定义实现。

### 4. 反爬虫机制

Wbi 签名（`recalculate_wbi`）、buvid 自动生成（`get_buvid`）、bili_ticket 获取（`get_bili_ticket`）等反爬逻辑入口定义在 `utils/_api.py`，反爬主体实现与参数缓存（`AntiSpiderCache`）位于 `utils/_anti_spider.py`。`request_settings` 全局管理代理、超时、SSL 验证等配置。

### 5. 异步事件系统

`AsyncEvent`（`utils/AsyncEvent.py`）是事件总线基类，`LiveRoom`（直播弹幕）、`RequestLog`（请求日志）等均继承它。使用 `@event.on("EVENT_NAME")` 注册监听器。

## 编码规范

### 风格

- **遵循 PEP 8**，使用 `ruff check` + `ruff format` 检查代码风格，`pyrefly check` 做类型检查（`scripts/lint.py` 一键执行，末尾含 `scripts/type_ratchet.py` 豁免错误码存量棘轮：豁免类别的存量计数只减不增，新增类型错误会被阻断）
- **类型存量棘轮维护义务**：修复存量类型错误后仅向下更新 `scripts/type_ratchet.py` 基线；某错误码基线清零后，须同步从 `pyproject.toml` 的 `[tool.pyrefly.errors]` 豁免表移除该条目并从脚本基线中删除，恢复默认启用
- **下划线命名**，与现有代码保持一致
- **全面类型注解**：函数参数、返回值均需类型注释
- **docstring 必须完整**：每个公共函数都应有中文 docstring（Args / Returns / Raises），因为 `scripts/doc_gen.py` 会从 docstring 自动生成文档
- **中英文之间加半角空格**（包括 docstring 和代码注释）

### 异步

- 所有 API 调用函数必须是 `async def`
- 禁止在库代码中使用 `asyncio.run()`（由调用方负责）
- 注意并发请求不要过快，会触发 412 风控

### 参数传递

- API 调用使用**关键字参数**（指名传参），不要用位置参数
- 新增参数优先考虑设置默认值，避免破坏性变更

### 异常

- 使用项目自定义异常体系（`bilibili_api/exceptions/`），不要直接 `raise Exception`
- 常用异常：`ArgsException`（参数错误）、`ResponseCodeException`（API 返回错误码）、`NetworkException`（网络错误）

## 提交规范

### Conventional Commits（强制）

Git Hook 会校验 commit message 格式：

```
<type>(<scope>)?: <description>

[optional body]

[optional footer]
```

**允许的 type：** `build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor` `release` `revert` `style` `test` `tests`

示例：
- `feat: 新增视频评论区关键词搜索`
- `fix(video): 修复 get_info 在无 bvid 时崩溃`
- `docs: 更新 Credential 获取方式说明`

### 破坏性变更

尽量避免。如必须，在 commit message 中标注：
```
fix!: Video.like() 参数变更

BREAKING CHANGE: Video.like() 移除了 deprecated 参数
```

### 提交粒度

一个提交只做一件事。修 bug + 加功能 = 两个提交。

## 开发流程

本项目使用 **uv** 管理依赖和虚拟环境。

1. `uv sync` — 创建 `.venv` 并安装全部依赖（含 dev 组：ruff / pyrefly / aiohttp / httpx / curl_cffi）
2. `uv run python install.py` — 初始化 Git Hooks（commit-msg + pre-commit）
3. 从 `dev` 分支切出新分支开发
4. 完成后运行 `uv run python scripts/lint.py`（门禁组成：`ruff check` → `ruff format --check` → tests/scripts 阻断检查 → `pyrefly check` → 豁免错误码存量棘轮 `scripts/type_ratchet.py`）；也可单独执行 `uv run ruff check ./bilibili_api/` + `uv run ruff format --check ./bilibili_api/` + `uv run pyrefly check ./bilibili_api/`，类型存量变更需另跑 `uv run python scripts/type_ratchet.py` 确认基线只减不增
5. 新增功能后运行 `uv run python scripts/doc_gen.py` 重新生成文档（脚本已兼容 Python 3.10+；依赖 mypy（含 stubgen）先生成 `.mypy_cache`，且 mypy 需以忽略错误的方式运行，否则含错误模块的缓存会被 mypy 删除）
6. 向 `dev` 分支发起 PR

> 没有 uv 的环境可回退到 `pip install -r requirements.txt` + 手动装 dev 工具。

## 测试

全部测试统一由 pytest 运行（异步用例由 pytest-asyncio 驱动，见 `pyproject.toml` 的 `[tool.pytest.ini_options]`）。集成用例由 `tests/conftest.py` 自动打上 `integration` 标记，缺凭据时自动 skip。

```bash
# 运行全部测试（无凭据时集成用例自动 skip，仅离线用例实际执行）
uv run pytest

# 仅离线快速路径（不触碰网络与真实账号，无需 BILI_* 环境变量）
uv run pytest -m "not integration"

# 仅集成测试（需配置下方 BILI_* 环境变量）
uv run pytest -m integration

# 只读集成子集（readonly 标记，无写操作；参与 PR 验证，反爬用例无需凭据）
uv run pytest -m readonly

# 运行指定模块测试
uv run pytest tests/test_video.py
```

集成测试凭据来源（优先级从高到低，由 `tests/conftest.py` 自动加载）：

1. **`.bilibili.cookie` 文件（推荐，本项目已配置）**：项目根目录下的 `.bilibili.cookie` 存放测试账号的完整 Cookie（浏览器导出的标准 Cookie 字符串，含 `SESSDATA` / `bili_jct` / `buvid3` / `buvid4` / `DedeUserID`）。每次测试直接 `uv run pytest` 即可自动使用它进行全量测试。**该文件已加入 `.gitignore`，严禁提交到仓库。**
2. **BILI_* 环境变量**（同名环境变量优先于 cookie 文件）：

```bash
BILI_SESSDATA=xxx        # SESSDATA cookie
BILI_CSRF=xxx            # bili_jct cookie
BILI_BUVID3=xxx          # BUVID3 cookie
BILI_DEDEUSERID=xxx      # DedeUserID cookie
BILI_RATELIMIT=1.5       # 用例间隔秒数（可选，防止触发 412 风控）
```

两者均缺失时，集成用例自动 skip，仅离线用例执行。

- 离线用例只验证纯本地逻辑（如 aid/bvid 互转、varint、纯解析函数），禁止在其中引入网络请求、真实凭据或会改变账号状态的操作；新增离线用例请放入 `tests/test_offline_*.py`
- 只读集成用例（`readonly` 标记，如 `tests/test_readonly_smoke.py`）仅允许 GET 式读请求与反爬虫参数获取，严禁写操作；该子集在 CI 的 `integration-readonly` 任务中参与 PR 验证，缺凭据时自动降级为警告而不阻塞合入
- 集成用例通过 `conftest.py` 的 `credential` fixture 获取登录态；模块级共享对象用 module 作用域 fixture 构建；同文件内用例按定义顺序执行，存在顺序依赖时不要重排用例

## 常见陷阱

- **412 Precondition Failed**：请求过快，需降低并发或设置代理 `request_settings.set_proxy(...)`
- **Wbi 签名失效**：B 站会不定期更新 Wbi 密钥，如遇大批 API 失效优先检查 `recalculate_wbi` 逻辑
- **Cookies 过期**：`Credential` 有 `check_refresh()` 方法可用于检查并刷新
- **请求库缺失**：至少需安装 aiohttp / httpx / curl_cffi 之一，否则初始化报错
- **b 站接口变更**：爬虫库的天然风险，API 可能随时失效，需跟进上游 `bilibili-API-collect` 的最新成果

## 关键依赖

| 依赖 | 用途 |
|------|------|
| `aiohttp` / `httpx` / `curl_cffi` | 异步 HTTP 客户端（三选一或多选） |
| `beautifulsoup4` + `lxml` | HTML 解析（专栏爬取等） |
| `yarl` | URL 处理 |
| `pycryptodomex` | 加密（RSA 密码登录、Wbi 签名等） |
| `PyJWT` | JWT 解析（用户信息） |
| `brotli` | Brotli 解压（直播弹幕） |
| `pillow` | 图片处理 |
| `qrcode` / `qrcode_terminal` | 二维码生成（扫码登录） |
| `APScheduler` | 定时任务（cookies 刷新等） |
| `pyyaml` | YAML 解析 |

## 不要做的事

- ❌ 不要直接修改 `docs/` 下的 API 文档，改 docstring 后用 `doc_gen.py` 生成
- ❌ 不要用 `pip install` 直接装包，统一用 `uv add` / `uv sync`
- ❌ 不要在库代码中硬编码凭据（SESSDATA 等）
- ❌ 不要用 `print()` 调试，用 `logging`
- ❌ 不要忽略 ruff check 报出的错误，不要跳过 `scripts/lint.py`
- ❌ 不要向 `main` 分支直接提交，PR 目标永远是 `dev`
- ❌ 不要使用位置参数调用 API 函数，统一用关键字参数
- ❌ 不要在异步代码中使用同步阻塞操作（`time.sleep`、`requests.get` 等）
