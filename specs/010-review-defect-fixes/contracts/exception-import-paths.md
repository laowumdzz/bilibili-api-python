# Contract: 异常导入路径兼容

**Feature**: 010-review-defect-fixes | **契约对象**：`bilibili_api.exceptions` 包的导入面（下游调用方视角）

本契约固化修复 4（FR-005 / SC-003）。22 条历史路径的完整清单与实现位置见 [data-model.md](../data-model.md) 实体 2。

## 导入面契约

### 子模块路径（恢复的历史契约）

首次提交（`99648df`）存在过的全部 22 个按类子模块路径 MUST 可导入：

```python
from bilibili_api.exceptions.ArgsException import ArgsException   # 17 个薄兼容模块之一
from bilibili_api.exceptions.ApiException import ApiException     # 5 个原生模块之一
```

- 17 个并入 `_simple.py` 的路径以薄兼容模块恢复：模块内仅 `from ._simple import <Name> as <Name>` 与 `__all__ = ["<Name>"]`，不含任何类定义。
- 5 个自有模块（`ApiException` / `CookiesRefreshException` / `ExClimbWuzhiException` / `NetworkException` / `ResponseCodeException`）原样存在。

### 同一性保证

- 任一路径导入得到的异常类与包级导出为**同一对象**（`is` 判定为真）——`except` 精确捕获在两种导入写法下行为一致。
- 异常类定义、继承关系（均派生自 `ApiException` 体系）、构造签名零改动。

### 包级导入面（不变）

```python
from bilibili_api.exceptions import ArgsException, ...   # 22 项，__all__ 集合与修复前完全一致
```

## 变更记录义务

兼容性恢复 MUST 在 `CHANGELOGS/UNRELEASED.md` 留痕：说明恢复了哪 17 个导入路径、背景（重构并入 `_simple.py` 造成未告知的兼容破坏）、薄兼容层语义（仅 re-export，未来如需废弃须另行裁决）。项目自身测试中既有的子模块路径导入写法（如 `ResponseCodeException`）即该写法真实存在于生态的佐证。

## 验证锚点

- 离线：`tests/test_offline_exceptions_compat.py` 逐一导入 22 条路径，断言导入成功、`is` 同一、包级 `__all__` 集合不变。
