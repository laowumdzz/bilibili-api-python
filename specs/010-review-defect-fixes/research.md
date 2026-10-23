# Research: 评审缺陷修复

**Feature**: 010-review-defect-fixes | **Date**: 2026-10-23

本文档记录规划阶段的代码现状核查结论与 8 项设计决策。全部决策基于对 HEAD `2e2fd63` 的实地代码核查（核查点在各决策中标注文件与行号），无未解决的 NEEDS CLARIFICATION。

## 现状核查结论（实证基础）

| # | 缺陷 | 实证位置 | 机制 |
|---|------|----------|------|
| 1 | 扫码轮询 dict 参数 TypeError | `bilibili_api/login_v2.py:510-517`（`x-bili-locale-json` / `x-bili-device-req-json` 以 dict 字面量传入 `update_params`）；`bilibili_api/utils/_api.py:228-232`（归一化循环对非 bool 非 None 值原样透传） | dict 值穿透到客户端层，默认 aiohttp 经 yarl 编码查询串时抛 `TypeError`（无效变量类型），请求未发出 |
| 2 | 构造参数请求头被清空 | `bilibili_api/utils/_api.py:182`（`__post_init__` 中 `self.headers = dict.fromkeys(self.headers.keys(), "")`）；唯一构造传 headers 的调用点 `bilibili_api/login_v2.py:646`（短信风控交换分支，无 `update_headers` 恢复） | `login_v2.py:96/301/342` 的 `headers=` 均为直连 `get_client().request(...)`，不经 `Api` 构造，不受影响 |
| 3 | 请求体布尔错位 | `bilibili_api/utils/_api.py:233-237`（data 循环内 `new_params[key] = int(value)`） | 一行笔误，布尔字段从请求体迁移到查询参数 |
| 4 | 异常子模块路径断裂 | `bilibili_api/exceptions/__init__.py`（17 个类自 `_simple` 导入、5 个自有模块）；首次提交 `99648df` 的 `exceptions/` 有 22 个按类模块 | 22 − 5 = 17 个路径失效；`docs/modules/` 无异常文档（doc_gen 顶层清单不遍历 mypy 缓存子目录，实证见 D5） |
| 5 | registry 类别映射缺失 | `scripts/sync_api_registry.py:58-92`（`CATEGORY_FILE` 无 `broadcast` / `cheese` / `opus`）；KeyError 点在 `resolve_target`（`scripts/sync_api_registry.py:239`） | 当前三类别条目 URL 均已存在，在 `main()` 主循环 `known_urls` 检查（`scripts/sync_api_registry.py:344`）即被跳过，未触达 `resolve_target`；新条目出现即 `KeyError` |

支撑事实：

- registry 基线 `df7a5f6`，顶层按类别目录，`broadcast/`（readme、video_room）、`cheese/`（info、videostream_url）、`opus/`（detail、features、rich_text_nodes、space）三目录齐备。
- `bilibili_api/data/api/` 已有 `cheese.json` 与 `opus.json`（映射落既有文件），无 `broadcast.json`（走同步脚本既有"新文件"路径，`scripts/sync_api_registry.py:379-382`，惰性新建）。
- 库内 JSON 字符串参数先例：`bilibili_api/user.py:595`、`bilibili_api/dynamic.py:721` 以手工序列化的紧凑 JSON 字符串传 `x-bili-device-req-json`——证明服务端接受该形态，且这两处不受统一层改动影响（值已是 str）。
- 既有测试打桩位置过高：`tests/test_offline_api_core.py:165-180` 以假 `_prepare_request` 隔离，未覆盖客户端编码边界（即 spec 指出的测试盲区）。
- `tests/test_offline_sync_utils.py` 测的是 `utils/sync.py` 装饰器，同步脚本 `scripts/sync_api_registry.py` 目前无任何测试。

## 决策

### D1. dict 参数序列化位置：请求准备统一层（`_prepare_request` 归一化循环）

- **Decision**: 在 `bilibili_api/utils/_api.py` 的 `_prepare_request` 初始归一化循环（params 分支）中，`isinstance(value, dict)` 时转为紧凑 JSON 字符串；`bilibili_api/login_v2.py` 调用点保持 dict 字面量不动。
- **Rationale**: spec 澄清 Q1 已裁决统一层方案，对全部调用点生效；序列化发生在 `_enc_dm` / `WbiManager` / `_enc_sign` 等反爬层之前，保证反爬层见到的 params 恒为标量；与 bool→int、None 剔除并列在同一循环，规则集中一处。
- **Alternatives considered**: ① 调用点手工 `json.dumps`（`user.py` / `dynamic.py` 模式）——已证明可行但散落，扫码轮询正是漏改的例子；② 客户端适配层（aiohttp / httpx 各自处理）——两份实现、注册的第三方客户端不受益、抽象层职责外溢。均否决。

### D2. 序列化口径：`json.dumps(value, ensure_ascii=False, separators=(",", ":"))`

- **Decision**: 紧凑分隔符 + 非 ASCII 以 UTF-8 原文保留；序列化异常（理论不可达：dict 内含不可序列化值）自然传播，不静默吞掉。
- **Rationale**: spec Edge Cases 明确要求紧凑分隔符与 UTF-8 保留；与浏览器实测行为及库内 `user.py:595` 手工先例（`{"platform":"web","device":"pc"}`）形态一致；`json` 已在 `_api.py` 导入。bool 分支在 dict 分支之前判定（bool 非 dict，顺序无歧义，保持 bool→int 优先级不变）。
- **Alternatives considered**: `ensure_ascii=True`（转义为 `\uXXXX`）——违背 UTF-8 保留要求，否决。列表值参数不处理——现状行为不变，超出 FR-002 范围。

### D3. 请求头修复：`__post_init__` 保留原值（`dict(self.headers)` 拷贝），不改调用点

- **Decision**: 删除 `__post_init__` 中对 headers 的占位清空（`bilibili_api/utils/_api.py:182`），改为值保留的浅拷贝；`login_v2.py:646` 调用点不加 `update_headers` 补丁。
- **Rationale**: FR-003 第一句是全局契约（"通过构造参数显式传入的自定义请求头 MUST 原样送达"），修复必须落在构造语义上；全库仅一个构造传 headers 的调用点（已核查），保留值不产生其他影响；`update_headers` 整体替换语义不变；浅拷贝避免 `Api` 实例与调用方字典共享可变状态（与 `original_data` / `original_params` 的既有拷贝习惯一致）。
- **Alternatives considered**: ① 仅在 `login_v2.py:646` 补 `update_headers`——局部修补，全局契约仍破，将来第二个构造传 headers 的调用点重蹈覆辙；② 同时移除 data / params / files 的占位清空——超出本特性范围（占位清空 + `update_*` 恢复是既有设计，仅 headers 因唯一调用点缺恢复步骤而成为缺陷），不做。

### D4. 请求体布尔归位：单行修正 `new_params[key]` → `new_data[key]`

- **Decision**: `bilibili_api/utils/_api.py` data 归一化循环中布尔分支写入 `new_data`；params 循环的 bool→int 与两侧 None 剔除行为不动。
- **Rationale**: 一行笔误对应一行修复；FR-004 全部三条子句（0/1 入请求体、查询参数不含该键、既有行为不变）由此满足；无备选方案空间。
- **Alternatives considered**: 无。

### D5. 异常兼容层：17 个静态薄模块（仅 re-export）+ CHANGELOGS 留痕

- **Decision**: 在 `bilibili_api/exceptions/` 下新增 17 个与历史同名的模块文件，每个仅含 `from ._simple import <Name> as <Name>` 与 `__all__ = ["<Name>"]` 及说明性模块 docstring；同时在 `CHANGELOGS/UNRELEASED.md` 记录恢复了哪些导入路径及原因。17 个类名清单：`ArgsException`、`CredentialNoAcTimeValueException`、`CredentialNoBiliJctException`、`CredentialNoBuvid3Exception`、`CredentialNoBuvid4Exception`、`CredentialNoDedeUserIDException`、`CredentialNoSessdataException`、`DanmakuClosedException`、`DynamicExceedImagesException`、`GeetestException`、`InitialStateException`、`LiveException`、`LoginError`、`ResponseException`、`StatementException`、`VideoUploadException`、`WbiRetryTimesExceedException`。
- **Rationale**: spec 澄清 Q3 裁决"恢复全部 17 个薄兼容层（仅 re-export，类对象与包级导出同一）"；静态文件可 grep、可审计、IDE 可跳转；`as` 冗余别名是 Python 惯用的 re-export 标记（ruff 认可）；包级 `__init__.py` 与 `__all__` 零改动，包级导入面不变（FR-005）。文档影响已实证排除：doc_gen 以 `os.listdir` 读取 mypy 缓存顶层清单，`exceptions` 是子目录形态，其中子模块永不进入文档生成循环，17 个新模块不产生 `docs/modules/` 漂移。
- **Alternatives considered**: ① `__init__.py` 内 importlib 动态注入 `sys.modules`——魔法式、不可静态分析、工具链（mypy / ruff / IDE）兼容性差，否决；② 仅文档告知破坏——已被澄清 Q3 否决；③ 恢复完整类定义（从 `_simple` 搬回）——违背重构收敛初衷且需双份维护，否决。

### D6. 同步脚本：补三类别映射 + 未映射类别"跳过 + 按类别聚合告警"

- **Decision**: `CATEGORY_FILE` 按字母序补 `"broadcast": "broadcast"`、`"cheese": "cheese"`、`"opus": "opus"`；`main()` 主循环在 `known_urls` / `used_urls` 检查之后、`resolve_target` 之前增加映射检查——类别既不在 `CATEGORY_FILE` 且 `(类别, 子主题)` 不在 `SUBTOPIC_OVERRIDES` 时按类别聚合计数并跳过；循环后对每个未映射类别输出 `logger.warning("跳过未映射类别 %s：%d 条待同步条目")`，汇总 info 行增加"无映射跳过"计数，与"已存在跳过"可区分。
- **Rationale**: spec 澄清 Q4 裁决"补齐三类别 + 保留跳过告警兜底"；`cheese` / `opus` 落既有文件、`broadcast` 走既有新文件路径（惰性新建，本特性不创建 `broadcast.json`）；检查点放在 URL 去重之后可保持"已存在条目不触达解析"的现状语义（SC-004 预览计数语义不变的前提）；聚合告警避免同一类别数十条逐条刷屏。
- **Alternatives considered**: ① 仅加兜底不补映射——违反澄清 Q4；② 在 `resolve_target` 内 try/except KeyError——异常流做常规控制，且无法按类别聚合计数；③ 告警逐条输出——刷屏，维护者难读。

### D7. 扫码轮询测试边界：本地回环 aiohttp 服务器走真实客户端栈

- **Decision**: 测试在 `127.0.0.1` 随机端口起 aiohttp 服务器，monkeypatch `API["qrcode"]["web"]["get_events"]["url"]` 指向回环地址，驱动真实 `QrCodeLogin.check_state()` → `Api.update_params` → `_prepare_request` → `get_client()`（默认 aiohttp）→ yarl 编码全链路；服务端断言收到的查询参数：全部为标量、两个结构化参数为合法紧凑 JSON 字符串（UTF-8）。修复前该用例因客户端编码抛 TypeError 而失败（服务端收不到请求），满足 SC-001"区分修复前后"。
- **Rationale**: FR-007 明确要求断言位置在"客户端编码边界"而非 `Api` 方法层——这正是既有测试盲区（现状核查：`test_offline_api_core.py` 以假 `_prepare_request` 隔离）；回环复现也是评审报告的复现手段。离线层"不触网"解释为不离开本机：`127.0.0.1` 属本机进程间通信，零凭据、零账号状态、零外网依赖，符合宪法 IV 离线用例边界（v1.2.1 PATCH 修订，2026-10-23：本机回环不视为网络请求）。
- **Alternatives considered**: ① 直接调用 yarl / aiohttp 的查询串编码函数断言——更轻，但绕过真实客户端栈，无法证明"请求真正发出"；② patch DNS 把 passport 域名指向回环——过重且污染面大。均否决。

### D8. 测试落位与 scripts 导入方式

- **Decision**: 四组测试按主题落位——`tests/test_offline_api_core.py` 扩展（params dict 序列化、headers 保留、data 布尔归位、None 剔除回归，断言 `_prepare_request` 输出）；`tests/test_offline_login_v2.py` 扩展（扫码轮回环用例）；新增 `tests/test_offline_exceptions_compat.py`（22 条历史路径逐一 `importlib.import_module`、`is` 同一性、包级 `__all__` 集合不变）；新增 `tests/test_offline_sync_api_registry.py`（`importlib.util.spec_from_file_location` 加载 scripts 下的脚本模块，monkeypatch 其 `REGISTRY_DIR` / `API_DIR` 模块常量指向 tmp 目录：已映射类别落位、未映射虚构类别跳过告警（caplog 断言含类别名与条目数）、三类别映射解析正确、dry-run 对真实 registry 输出不变仅作手动验收步骤见 quickstart.md）。
- **Rationale**: 离线用例命名约定 `test_offline_*.py`（宪法 IV）；`scripts/` 非包成员，测试需按文件路径加载（无既有先例，`test_offline_sync_utils.py` 测的是 `utils/sync.py` 包模块而非脚本）；同步脚本测试不依赖真实 registry 目录（tmp fixture 自包含，新克隆环境可跑）。
- **Alternatives considered**: ① 全部新用例集中一个新文件——主题混杂，违背按模块落位习惯；② 给 `scripts/` 加 `__init__.py` 使其成包——改变仓库结构仅为测试便利，否决。
