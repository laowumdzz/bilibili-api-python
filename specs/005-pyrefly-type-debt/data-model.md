# Data Model: 清零 pyrefly 存量类型错误（1064 条）

**Feature**: 005-pyrefly-type-debt | **Date**: 2026-09-25

本特性不引入任何运行时数据存储（无数据库、无新文件格式）。所涉及的
"数据"是**过程台账**：错误存量、批次与退役状态。台账的可信来源是两处
既有 git 内工件——`scripts/type_ratchet.py` 的 `BASELINE` 常量与
`pyproject.toml` 的 `[tool.pyrefly.errors]` 表（以及每次验收运行的
实测命令输出）。本文档定义这些实体的字段与状态机，作为批次验收与
tasks 编排的概念模型。

## 实体

### ErrorInstance（错误实例）

单条类型错误，验收计数的原子单位。

| 字段 | 说明 | 示例 |
|------|------|------|
| code | 错误码（9 豁免码或 2 残留码之一） | bad-return |
| file | 相对仓库根的源文件路径 | bilibili_api/user.py |
| line / col | 位置（min-text 输出解析） | 91 / 20-45 |
| message | 错误消息模板（用于根因聚类） | 联合类型不可赋给声明返回类型 |
| root_cause | 归因（A: Api 联合类型传导 / B: 解码累加器 / C: 真 bug·注解错误 / R: 残留码） | A |

约束：同一 `(file, line, code)` 可叠加多条；批次计数以 ERROR 行数为准
（research.md R8）。

### CodeLedger（错误码台账行）

每个错误码一行，棘轮校验的记账单位。

| 字段 | 说明 |
|------|------|
| code | 错误码 |
| baseline | 棘轮脚本 `BASELINE` 中的冻结上限（只减不增） |
| measured | 最近一次同口径命令实测条数 |
| state | 见下方状态机 |

状态机：

```text
ACTIVE(measured ≤ baseline, baseline > 0)
  ├─ 批次修复 measured 下降 ──► ACTIVE（同步下调 baseline）
  ├─ measured == 0 ───────────► PENDING_RETIRE（待退役窗口）
  └─ measured > baseline ─────► VIOLATION（棘轮阻断，禁止合入）
PENDING_RETIRE
  └─ 同批次内删除 baseline 条目 + 移除 pyproject 豁免行 ──► RETIRED
RETIRED（终态；该码恢复默认拦截，任何新错误直接挂门禁）
```

约束（来自 spec FR-003/SC-006）：`PENDING_RETIRE` 不得跨批次存续——
清零与退役成对发生；`baseline` 任何上调即 `VIOLATION`。

### Batch（修复批次）

一次独立可合入的交付单元（spec Key Entities）。

| 字段 | 说明 |
|------|------|
| id | 批次号（0 校准 / 1 地基 / 2..N 模块清扫 / F 收尾） |
| scope | 覆盖的根因与文件清单（如"批次 3：login_v2.py 全量迁移"） |
| codes_touched | 涉及错误码集合 |
| expected_delta | 预期各码下降数（依实测分布预估，允许修正） |
| carry | 同批成对完成的退役动作（如有） |
| real_bugs | 批内发现并拆分处置的真 bug（引用独立提交） |

约束：每批次必须门禁全绿 + 棘轮不回升才可合入（spec FR-006/SC-006）；
真 bug 不并入类型修复提交（spec FR-005/FR-009）。

### RealBugSplit（真 bug 拆分记录）

根因 C 实例的处置痕迹（research.md R1 表格的运行态）。

| 字段 | 说明 |
|------|------|
| location | file:line |
| symptom | 静态错误表现 |
| diagnosis | 定性（漏 await / 注解错误 / 签名错误 / 兼容雷区） |
| action | 独立提交哈希或"并入批次说明"（仅注解放宽类） |
| compat_impact | 无 / 类型层纠错（记录） / 破坏性（目标为零） |

## 实体关系

- `Batch` 1..* `ErrorInstance`（批次消除的错误集合，经 measured 差值体现）
- `Batch` 0..1 `CodeLedger` 退役动作（`carry`）
- `RealBugSplit` *..1 `Batch`（发现于某批次，处置独立于该批次提交）

## 存储映射

| 概念实体 | 物理载体 |
|----------|----------|
| CodeLedger.baseline | `scripts/type_ratchet.py` `BASELINE` 常量 |
| CodeLedger 豁免态 | `pyproject.toml` `[tool.pyrefly.errors]` 行存在性 |
| measured | 每次验收运行的命令输出（不落盘，台账以差值记录在批次提交说明） |
| Batch / RealBugSplit | git 提交序列本身（提交说明引用批次号与拆分依据） |
