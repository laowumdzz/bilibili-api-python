# Phase 0 Research: 移除 CurlCFFI 客户端适配

**Feature**: 009-remove-curlcffi-client | **Date**: 2026-10-11

规格无遗留 NEEDS CLARIFICATION（澄清会话已裁决移除节奏与报错形态两项）。本章记录代码库机制核查结论与实现层设计决策。

## R1 自动选择机制核查（决策依据）

**发现**（`bilibili_api/__init__.py` L175-186 `__register_all_clients()`）：

- 倒序遍历 `ALL_PROVIDED_CLIENTS[::-1]`（httpx → aiohttp → curl_cffi），逐项 `importlib.import_module(module)` 探测第三方库是否可导入（`ModuleNotFoundError` 则跳过），随后 `register_client(module, ...)`——`register_client` 内部会调用 `select_client(name)`，**最后注册者胜出**，故清单首项（curl_cffi）成为默认。
- 移除 curl 条目后，倒序遍历变为 httpx → aiohttp，aiohttp 最后注册成为默认；aiohttp 不可导入时回退 httpx；两者皆无时 `selected_client` 保持空串，`get_client()` 等走"尚未安装"错误路径。
- `aiohttp>=3.9` 是 `[project.dependencies]` 硬性依赖：正常 pip/uv 安装路径下 aiohttp 恒可用。spec 中"仅安装 httpx"的环境只能以手动卸载 aiohttp 或测试内注入模拟达成——属能力验证而非常规路径，SC-001 仍然有效。

**结论**：`__register_all_clients()` 是数据驱动机制，`ALL_PROVIDED_CLIENTS` 缩短后自动适应，`bilibili_api/__init__.py` 无需改动。

- Decision: 只改 `clients/__init__.py` 清单，不动注册函数
- Rationale: 机制本身与具体客户端解耦；改清单即改行为，最小改动面
- Alternatives considered: 在注册函数中硬编码新优先级（否决——引入冗余耦合，违背现有数据驱动设计）

## R2 错误信息设计（FR-003 / FR-009 落地）

**现状**（`bilibili_api/utils/_session.py`）：

- `select_client(name)`：`raise ArgsException(f"未注册过 {name}。")` —— 不列出可用项，不满足 FR-003"列出当前可选内置客户端"。
- `get_selected_client()` / `get_available_settings()` / `get_client()` 三处：`"尚未安装第三方请求库或未注册自定义第三方请求库。\n$ pip3 install (curl_cffi|httpx|aiohttp)"` —— 残留 curl_cffi 安装指引，违反 FR-009。

- Decision:
  1. 三处"尚未安装"文本改为 `$ pip3 install (aiohttp|httpx)`，其余措辞不变。
  2. `select_client` 的未注册消息增强为：`未注册过 {name}。当前已注册的客户端：{", ".join(sorted(sessions.keys()))}（或通过 register_client() 注册自定义客户端）。`；`sessions` 为空时退化为既有"尚未安装"文本。清单按字典序排序输出，保证消息确定性、不依赖注册顺序（倒序注册的实际插入序为 httpx, aiohttp，排序后呈现为 aiohttp, httpx）。
- Rationale: 通用注册机制的消息不点名任何具体客户端（对 curl_cffi 与任意自定义名一视同仁）；"该客户端已不再内置适配"的语义由变更记录与文档承载（spec 澄清裁决"干净移除，迁移指引由文档承载"）；消息增强满足 FR-003 的"列出当前可选"要求且对所有未注册名一致成立。
- Alternatives considered: 仅为 "curl_cffi" 这一名字特判输出"已移除"文案（否决——机制层不应感知具体业务名，且与"干净移除不留残码"裁决相悖）；消息保持原样仅靠文档（否决——不满足 FR-003 的 MUST）。

## R3 依赖与锁文件

**发现**：curl-cffi 在 `uv.lock` 中仅两处引用——本项目 `[package.dev-dependencies]` 与 `[package.metadata.requires-dev]`；无任何其他包依赖它。运行时依赖从未包含（`[project.dependencies]` 无 curl-cffi）。

- Decision: `pyproject.toml` dev 组删除 `curl-cffi>=0.16.3`；`requirements.txt` 删除 `curl_cffi>=0.8.1` 行；随后 `uv sync` 再生锁文件（curl-cffi 整条消失）。`uv.lock` 不手改。
- Rationale: 锁文件是派生物；curl-cffi 无其余引用方，sync 后环境彻底无该包，与"已安装但被静默忽略"的边界用例可在测试中以模拟方式验证而不依赖真实安装。
- Alternatives considered: dev 组保留 curl-cffi 专供边界测试（否决——违反 FR-004 且锁文件长期携带无用二进制依赖）。

## R4 测试改造方案（FR-007）

**现状**：

- `tests/conftest.py` `_install_request_counter()`：包装清单含 `("bilibili_api.clients.CurlCFFIClient", "CurlCFFIClient")`，文件删除后该 import 必炸，必须移除；docstring"对三个内置客户端"同步改"两个"。
- `tests/test_offline_client_timeout_semantics.py`：`TestCurlCFFIClientTimeout` 类（4 用例）+ 模块 docstring 中 curl_cffi 归一化注记（含实测背景日期行）。aiohttp / httpx 部分保留。
- `tests/test_offline_ws_handle_leak.py`：`HAS_CURL_CFFI` 探测块、`FakeCurlWs`、`make_bare_curl_client()`、4 个 `@pytest.mark.skipif(not HAS_CURL_CFFI, ...)` 用例全部随适配删除；aiohttp 4 用例保留。

- Decision: 新增 `tests/test_offline_client_selection.py` 覆盖 FR-007 三场景（纯本地逻辑，不发请求）：
  1. **清单契约**：`ALL_PROVIDED_CLIENTS` 恰为 `aiohttp`、`httpx` 两项且相对顺序 aiohttp 在前，均不含 curl。
  2. **回退与默认选择**：以 importlib 打桩模拟"第三方库可/不可导入"，验证倒序注册后默认选中 aiohttp；模拟 aiohttp 缺失时回退 httpx；全部缺失时 `selected_client` 为空、`get_client()` 抛 `ArgsException` 且消息含 `(aiohttp|httpx)`。
  3. **干净移除**：`importlib.import_module("bilibili_api.clients.CurlCFFIClient")` 抛 `ModuleNotFoundError`；`select_client("curl_cffi")` 抛 `ArgsException` 且消息含"当前已注册的客户端"列表；`register_client("curl_cffi", <stub>)` 注册同名自定义客户端后 `select_client("curl_cffi")` 正常生效（FR-005），用例结束 `unregister_client` 还原。
- Rationale: 三场景分别锚定 FR-001+FR-002、FR-003+FR-009、FR-005 与导入路径裁决；全部可离线执行（打桩对象均为本地模块表/导入系统，无网络、无凭据）。
- Alternatives considered: 并入既有 timeout 语义文件（否决——该文件主题是超时归一化，混入选择契约降低可读性）；仅靠集成测试验证（否决——集成缺凭据即 skip，离线红线要求该契约恒可验证）。

## R5 文档与治理文本更新策略（FR-006）

**足迹核查**（grep 全库，排除豁免项后）：

| 文件 | 现状 | 处置 |
|---|---|---|
| `README.md` | L44 特性清单、L65/74-75 安装、L157 优先级、L164 select_client 示例、L169-175 impersonate 段 | 编辑：删 curl 项；优先级改 aiohttp > httpx；impersonate 段整体删除 |
| `docs/README.md` | 与 README.md 镜像（L44/61/70-71/153/160/165-171） | 编辑：同上镜像同步 |
| `docs/request_client.md` | L13 内置客户端对比表含 curl 行、L17/22 impersonate 说明、L49/51/93/129 泛述提及、L229-251 自定义客户端教程以 `CurlCFFIClient`/impersonate 为 worked example | 编辑：对比表删 curl 行；教程重写语境——curl_cffi 明确标注为"第三方自定义接入示例"（恰好演示 FR-005：内置移除后自定义接入仍可行），删除"模块默认携带 CurlCFFIClient"表述 |
| `docs/configuration.md` | L9 设置支持表含 curl_cffi 列（impersonate 行） | 编辑：删 curl 列；impersonate 行随列删除；http2 行保留（httpx 仍支持） |
| `docs/examples/audio.md` | L6 `from curl_cffi import requests`、L29 "默认使用 curl_cffi" | 编辑：示例改用 aiohttp；注释改"默认使用 aiohttp" |
| `.github/ISSUE_TEMPLATE/troubleshooting.md` | L24 请求库候选项 | 编辑：删 curl_cffi |
| `AGENTS.md` | L7 概览、L51 结构树、L105 优先级、L180 uv sync 清单、L288 陷阱、L295 依赖表（6 处） | 编辑：全部同步为两客户端实态 |
| `.specify/memory/constitution.md` | 原则 I L33 `curl_cffi > aiohttp > httpx` | 修订：按宪法修订程序独立提交（R6） |
| `docs/modules/client.md` | doc_gen 生成页含 CurlCFFIClient 段 | 重生成入库（非手工编辑，符合"docs/ API 文档不手编"红线） |

- Decision: 如上表处置；`docs/request_client.md` 的自定义客户端教程保留 curl_cffi 作为示例第三方库但重写语境。
- Rationale: 教程演示"如何为任意第三方库写适配"，保留原示例可最大化教学连续性，且明确"内置已不携带、自定义接入可行"恰好呼应 FR-005；其余处不留任何"内置可用"暗示。
- Alternatives considered: 教程示例换成虚构库（否决——失去真实可跑性，且掩盖"同名自定义注册仍可行"的契约演示价值）。

## R6 宪法修订与提交策略

- Decision:
  1. 宪法原则 I 的优先级链描述更新为 `aiohttp > httpx`，版本 1.0.1 → 1.0.2（PATCH，措辞/事实澄清，原则集合不变），文件头部附 Sync Impact Report；以独立提交 `docs: amend constitution to v1.0.2 ...` 处理（宪法 Governance 条款要求），随本特性提交序列一并入库。
  2. 提交拆分（一个提交只做一件事）：① `refactor!: 移除 CurlCFFI 客户端适配` —— 库代码 + 依赖 + 测试 + `docs/modules/client.md` 重生成，BREAKING CHANGE footer 写明影响面与迁移方式（FR-008）；② `docs: 同步移除 CurlCFFI 的用户文档与治理文本表述` —— README/docs/AGENTS/troubleshooting/CHANGELOGS 新节；③ `docs: amend constitution to v1.0.2 ...`。版本号递增不在本特性范围（spec Assumptions）。
- Rationale: 修订程序与提交粒度均为宪法/AGENTS 硬性要求；变更记录新节承载 BREAKING CHANGE 的下游告知义务。
- Alternatives considered: 宪法修订与文档合并一个提交（否决——宪法要求修订 MUST 通过独立提交完成）。

## R7 豁免清单（不回改的历史记录）

以下文件含 curl_cffi 字样但属历史事实记录，按 spec FR-006 豁免：`CHANGELOGS/v17.md`、`CHANGELOGS/v18.md`、`REFACTORING.spec.md`（上游时代重构设计存档）、`specs/001-*` `specs/002-*` `specs/005-*` `specs/008-*` 及其子工件、本特性 `specs/009-*/` 自身（描述移除这一行为本身）。

## R8 impersonate 设置面消亡核查

**发现**：每客户端设置项由 `ALL_PROVIDED_CLIENTS` 第三元组注入 `client_settings`；`DEFAULT_SETTINGS`（`_types.py` L206）仅 `proxy/timeout/verify_ssl/trust_env`，不含 impersonate。`request_settings.set(name, value)` 不做名称白名单校验（存入即向活跃客户端广播 `client[name] = value`），但公开文档中的唯一使用入口是 curl_cffi 段落。

- Decision: 不改 `request_settings` 代码；随文档删除 impersonate 使用指引（R5），设置面自然随 curl 适配消亡；`http2` 设置项保留（httpx 客户端仍声明）。
- Rationale: 机制层无 curl 特判代码可删；移除声明源即移除能力面，与"干净移除"一致。
- Alternatives considered: 为 `request_settings.set` 加未知设置名校验（否决——超出本特性范围的行为增强，留待独立特性）。
