# Phase 1 Data Model: 移除足迹清单模型

**Feature**: 009-remove-curlcffi-client | **Date**: 2026-10-11

本特性不引入数据实体；该模型刻画"移除足迹"——每个受影响表面的现状、目标态与变更类型，供 tasks 拆分与验收比对。变更类型：**DELETE**（整文件删除）/ **EDIT**（就地修改）/ **REGEN**（工具再生成）/ **SYNC**（uv 再生）/ **AMEND**（宪法修订程序）/ **APPEND**（新增节/文件）/ **EXEMPT**（豁免不回改）。

## 1. 库代码（运行时行为面）

| # | 表面 | 现状 | 目标态 | 类型 |
|---|------|------|--------|------|
| C1 | `bilibili_api/clients/CurlCFFIClient.py` | CurlCFFI 适配实现（`BiliAPIClient` 子类，含 WS/下载封装） | 文件不存在；导入 `bilibili_api.clients.CurlCFFIClient` 抛 `ModuleNotFoundError`（标准语义，无报错桩） | DELETE |
| C2 | `bilibili_api/clients/__init__.py` `ALL_PROVIDED_CLIENTS` | 三元组清单：curl_cffi（含 `impersonate`/`http2`/`chunk_size` 设置）、aiohttp、httpx | 两元组清单：aiohttp（`chunk_size`）、httpx（`http2`、`chunk_size`），相对顺序不变 | EDIT |
| C3 | `bilibili_api/utils/_session.py` `select_client` | `未注册过 {name}。` | `未注册过 {name}。当前已注册的客户端：{清单}（或通过 register_client() 注册自定义客户端）。`；空清单退化为"尚未安装"文本；异常类型仍 `ArgsException` | EDIT |
| C4 | `bilibili_api/utils/_session.py` `get_selected_client` / `get_available_settings` / `get_client` | 提示文本 `$ pip3 install (curl_cffi\|httpx\|aiohttp)`（3 处） | `$ pip3 install (aiohttp\|httpx)`（3 处一致） | EDIT |
| C5 | `bilibili_api/__init__.py` `__register_all_clients` | 倒序注册、最后注册者胜出 | **不改动**——清单缩短后自动适应：默认选中 aiohttp，aiohttp 缺失回退 httpx | —（验证对象） |

## 2. 依赖与锁

| # | 表面 | 现状 | 目标态 | 类型 |
|---|------|------|--------|------|
| D1 | `pyproject.toml` dev 组 | `curl-cffi>=0.16.3` | 无该行；运行时依赖本就不含 curl-cffi（`aiohttp>=3.9` 硬依赖保留） | EDIT |
| D2 | `requirements.txt` | `curl_cffi>=0.8.1`（L14） | 无该行 | EDIT |
| D3 | `uv.lock` | curl-cffi 包条目 + 本项目 dev 引用（无其他引用方） | curl-cffi 整条消失 | SYNC |

## 3. 测试（离线红线：无网络、无凭据、不改账号状态）

| # | 表面 | 现状 | 目标态 | 类型 |
|---|------|------|--------|------|
| T1 | `tests/conftest.py` `_install_request_counter` | 包装清单 3 项含 CurlCFFIClient；docstring"三个内置客户端" | 清单 2 项；docstring"两个内置客户端" | EDIT |
| T2 | `tests/test_offline_client_timeout_semantics.py` | `TestCurlCFFIClientTimeout`（4 用例）+ docstring curl 注记与 `CURL_CFFI_INFINITE` 常量〔勘误 2026-10-11〕实测该类为 3 用例，curl 相关用例合计 3+4=7 而非 4+4=8（WS 泄漏 4 例无误），以 tasks.md Implementation Completion Record T001 为据 | 删 curl 类/常量/注记；aiohttp、httpx 用例与归一化断言保留 | EDIT |
| T3 | `tests/test_offline_ws_handle_leak.py` | `HAS_CURL_CFFI` 块、`FakeCurlWs`、`make_bare_curl_client`、4 个 curl 用例 | 全部删除；aiohttp 4 用例保留 | EDIT |
| T4 | `tests/test_offline_client_selection.py` | 不存在 | FR-007 三场景离线覆盖：①清单契约（恰 aiohttp/httpx 两项且有序）②回退与默认选择（打桩导入：默认 aiohttp / 缺失回退 httpx / 全缺报"尚未安装(aiohttp\|httpx)"）③干净移除（模块导入 `ModuleNotFoundError`；`select_client("curl_cffi")` 报错含已注册清单；同名自定义注册生效并可注销还原） | APPEND |

## 4. 用户文档与门面

| # | 表面 | 现状 | 目标态 | 类型 |
|---|------|------|--------|------|
| U1 | `README.md` | 特性清单/安装/优先级/select_client 示例/impersonate 段含 curl（L44/65/74-75/157/164/169-175） | 两客户端实态；优先级 aiohttp > httpx；impersonate 段删除 | EDIT |
| U2 | `docs/README.md` | 与 U1 镜像内容 | 与 U1 同步 | EDIT |
| U3 | `docs/request_client.md` | 对比表 curl 行（L13）、impersonate 说明（L17/22）、泛述提及（L49/51/93/129）、自定义教程以 CurlCFFIClient 为例（L229-251） | 对比表删 curl 行；泛述更新；教程保留 curl_cffi 为"第三方自定义接入示例"并删"模块默认携带"表述 | EDIT |
| U4 | `docs/configuration.md` | 设置支持表含 curl_cffi 列与 impersonate 行（L9 起） | 删 curl 列与 impersonate 行；http2 行保留（httpx） | EDIT |
| U5 | `docs/examples/audio.md` | `from curl_cffi import requests`（L6）、"默认使用 curl_cffi"（L29） | 示例改 aiohttp；注释改"默认使用 aiohttp" | EDIT |
| U6 | `.github/ISSUE_TEMPLATE/troubleshooting.md` | 候选项"curl_cffi / httpx / aiohttp / ..."（L24） | "aiohttp / httpx / ..." | EDIT |
| U7 | `docs/modules/client.md` | 生成页含 CurlCFFIClient 段 | 重跑 `scripts/doc_gen.py` 后不含；入库〔勘误 2026-10-11〕本行前提与实态不符：`clients` 包从未进入 doc_gen 生成域，`docs/modules/client.md` 记录的是 `client.py`（IP 终端模块）且从不包含 CurlCFFIClient 段，重跑 doc_gen 对该页实为 no-op；本特性实际再生成页为 `docs/modules/bilibili_api.md`（docstring 单行兼容修复 dc986da 随附）——原文保留备查，详见 tasks.md Implementation Completion Record T010/T014 | REGEN |
| U8 | `CHANGELOGS/` | 无本期记录 | 新版本节记录移除、影响面与迁移方式（BREAKING CHANGE 告知载体） | APPEND |

## 5. 治理文本

| # | 表面 | 现状 | 目标态 | 类型 |
|---|------|------|--------|------|
| G1 | `AGENTS.md` | 概览（L7）、结构树（L51）、优先级（L105）、uv sync 清单（L180）、陷阱（L288）、依赖表（L295）共 6 处含 curl | 全部同步为 aiohttp > httpx 两客户端实态 | EDIT |
| G2 | `.specify/memory/constitution.md` | 原则 I `curl_cffi > aiohttp > httpx`（L33） | `aiohttp > httpx`；版本 1.0.1 → 1.0.2 + Sync Impact Report；独立提交 | AMEND |

## 6. 豁免清单（EXEMPT，验证时排除）

`CHANGELOGS/v17.md`、`CHANGELOGS/v18.md`、`REFACTORING.spec.md`、`specs/001-*`、`specs/002-*`、`specs/005-*`、`specs/008-*`、`specs/009-*`（本特性自述）、`bilibili-api-registry/`（独立嵌套仓库，与客户端适配无关）。〔2026-10-11 勘误扩充，与 quickstart §4 豁免保持一致〕`CHANGELOGS/UNRELEASED.md`（移除记录本体）、`docs/request_client.md` 自定义客户端教程节（research R5 裁决的"第三方自定义接入示例"教学语境；节外命中仍须人工分类）、`tests/test_offline_client_selection.py`（FR-007 移除契约锚定断言）、`.specify/memory/constitution.md`（头部 Sync Impact Report 的 from→to 修订记载）。

## 状态一致性规则

- C1 删除后，T1/T4 与 C2/C3/C4 构成闭环：任何一处遗漏都会被 T4 的对应断言或 lint 门禁（docs 漂移）捕获。
- U1 与 U2 为镜像内容，必须同改，验收时逐行比对两文件的 curl 残留。
- G2 修订必须在 G1 之后或同批完成，避免治理文本自相矛盾。
