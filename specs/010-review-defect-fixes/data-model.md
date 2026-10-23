# Data Model: 评审缺陷修复

**Feature**: 010-review-defect-fixes | **Date**: 2026-10-23

本特性为缺陷修复，无运行时持久化实体；"数据模型"在此表达三组结构性契约：请求准备层的归一化规则（修复 1/2/3 的行为定义）、异常导入路径映射（修复 4）、registry 类别映射（修复 5）。权威行为需求见 [spec.md](spec.md) FR-001–FR-007。

## 实体 1：请求准备归一化规则（`Api._prepare_request`）

调用方传入的 `params` / `data` 在请求准备阶段经统一归一化，输出仅含可编码标量。归一化在 `_enc_dm` / Wbi / `_enc_sign` 等反爬层之前完成，反爬层见到的参数恒为标量。

### params（查询参数）归一化表

| 输入值类型 | 输出形态 | 规则来源 |
|-----------|----------|----------|
| `bool` | `int(value)`（0/1） | 既有行为，不变（FR-004） |
| `dict` | `json.dumps(value, ensure_ascii=False, separators=(",", ":"))` 紧凑 JSON 字符串 | **新增**（FR-002 / 修复 1） |
| `None` | 键剔除 | 既有行为，不变（FR-004） |
| 其余（str/int/float） | 原样保留 | 既有行为，不变 |

约束：

- 判定顺序：`bool` 分支优先于 `dict` 分支（bool 非 dict，语义无交集；保持 bool→int 优先级不变）。
- dict 内含不可序列化值时 `json.dumps` 抛出的异常自然传播（按普通参数错误处理，不静默吞掉——spec Edge Cases）。
- dict 内嵌套 dict / list 按 JSON 语义整体序列化为一个字符串（不再是"仅一层"）。
- 序列化产物是合法 JSON：UTF-8 内容原文保留、紧凑分隔符、无 Python repr 形态（单引号）。

### data（请求体）归一化表

| 输入值类型 | 输出形态 | 规则来源 |
|-----------|----------|----------|
| `bool` | `int(value)`（0/1），**保留在 data** | **修复**：原错写入 params（FR-004 / 修复 3） |
| `None` | 键剔除 | 既有行为，不变 |
| 其余 | 原样保留 | 既有行为，不变 |

约束：`json_body=True` 场景下归一化后的 data 再整体 `json.dumps`，布尔已先转 0/1，行为自洽且不变。

### headers（请求头）生命周期（状态转移）

```text
调用方构造 Api(headers={...})
  → __post_init__: self.headers = 浅拷贝（值原样保留）   [修复 2：原为占位清空为 ""]
  → update_headers(**kwargs)（可选）: 整体替换
  → _prepare_request: 非空 dict 原样作为请求头；空 dict 时回落全局 HEADERS
```

- 值仅在调用方本人传空串时为空串（FR-003 / 验收场景 2-1）。
- `Api` 实例不与调用方传入的字典共享可变状态（浅拷贝隔离）。

## 实体 2：异常导入路径映射（22 条历史路径）

首次提交（`99648df`）存在过的全部按类子模块路径及其现状：

| # | 导入路径（`bilibili_api.exceptions.` 前缀） | 实现位置 | 兼容层 |
|---|---------------------------------------------|----------|--------|
| 1 | `ApiException` | 自有模块 | 不需要（原生存在） |
| 2 | `ArgsException` | `_simple.py` | **新增薄模块** |
| 3 | `CookiesRefreshException` | 自有模块 | 不需要 |
| 4 | `CredentialNoAcTimeValueException` | `_simple.py` | **新增薄模块** |
| 5 | `CredentialNoBiliJctException` | `_simple.py` | **新增薄模块** |
| 6 | `CredentialNoBuvid3Exception` | `_simple.py` | **新增薄模块** |
| 7 | `CredentialNoBuvid4Exception` | `_simple.py` | **新增薄模块** |
| 8 | `CredentialNoDedeUserIDException` | `_simple.py` | **新增薄模块** |
| 9 | `CredentialNoSessdataException` | `_simple.py` | **新增薄模块** |
| 10 | `DanmakuClosedException` | `_simple.py` | **新增薄模块** |
| 11 | `DynamicExceedImagesException` | `_simple.py` | **新增薄模块** |
| 12 | `ExClimbWuzhiException` | 自有模块 | 不需要 |
| 13 | `GeetestException` | `_simple.py` | **新增薄模块** |
| 14 | `InitialStateException` | `_simple.py` | **新增薄模块** |
| 15 | `LiveException` | `_simple.py` | **新增薄模块** |
| 16 | `LoginError` | `_simple.py` | **新增薄模块** |
| 17 | `NetworkException` | 自有模块 | 不需要 |
| 18 | `ResponseCodeException` | 自有模块 | 不需要 |
| 19 | `ResponseException` | `_simple.py` | **新增薄模块** |
| 20 | `StatementException` | `_simple.py` | **新增薄模块** |
| 21 | `VideoUploadException` | `_simple.py` | **新增薄模块** |
| 22 | `WbiRetryTimesExceedException` | `_simple.py` | **新增薄模块** |

薄模块结构（17 个同构）：

```python
"""<说明性 docstring：历史上承载类定义，重构后仅 re-export 同一类对象>"""
from ._simple import <Name> as <Name>

__all__ = ["<Name>"]
```

验证规则（不变式）：

- `importlib.import_module("bilibili_api.exceptions.<Name>").<Name>` 与包级导出 `is` 同一（FR-005 / SC-003）。
- 包级 `__init__.py` 与 `__all__`（22 项）零改动。
- 异常类定义、继承关系、构造签名零改动。

## 实体 3：registry 类别映射（`CATEGORY_FILE` + 兜底语义）

### 映射表增量

| registry 类别 | 目标文件（`bilibili_api/data/api/`） | 落位方式 |
|---------------|--------------------------------------|----------|
| `broadcast` | `broadcast.json` | 无既有文件，出现待同步条目时经同步惰性新建 |
| `cheese` | `cheese.json` | 既有文件 |
| `opus` | `opus.json` | 既有文件 |

（既有 33 项映射不变；`SUBTOPIC_OVERRIDES` / `SECTION_PREFIX` 不变。）

### 条目分流状态机（每条 REST 条目）

```text
load_registry() 逐条读取（附 _category / _subtopic）
  → URL 已存在于 data/api？ ──是──→ 跳过（skipped_known 计数；三类别现状全部走此路）
                                    │否
  → registry 内重复 URL？   ──是──→ 跳过（skipped_dup 计数）
                                    │否
  → 类别可解析？（CATEGORY_FILE 命中 或 SUBTOPIC_OVERRIDES 命中）
                          ──否──→ 跳过（按类别聚合计数；循环后逐类别 warning，含类别名与条目数）  [新增兜底]
                                    │是
  → resolve_target() → (目标文件, section) → 追加条目
```

输出可区分性（spec Edge Cases）：汇总 info 行四个计数——已存在 / registry 内重复 / **无映射跳过** / 本次新增——任意两者不混淆；未映射类别另有独立 warning 行。

不变式：

- 当前全量 registry（基线 `df7a5f6`）预览计数语义与修复前一致：609 已存在、0 新增、0 无映射跳过（三类别条目全部命中 `known_urls`；汇总行新增"无映射跳过"计数项为设计内变更）。
- `broadcast.json` 在本特性提交中不被创建（目录中无此文件；仅当 registry 未来出现 broadcast 新条目时生成）。
- 纯增量契约不变：已存在条目不动、gRPC 与 `method=OTHER` 跳过、registry 元数据不进入接口定义。
