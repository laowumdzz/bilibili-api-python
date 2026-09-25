# Contract: 类型门禁工具链（本特性交付后的终态契约）

**Feature**: 005-pyrefly-type-debt | **Kind**: 工具链/配置契约

本特性改造的类型门禁体系，交付终态须满足以下契约。这是 spec FR-010 /
SC-001/002/003 的可执行化表述。

## 测量口径（单一可信来源）

```bash
uv run pyrefly check ./bilibili_api/ \
  --error bad-argument-type,bad-assignment,bad-function-definition,bad-index,bad-override,bad-return,missing-attribute,not-iterable,unsupported-operation \
  --output-format min-text --color never
```

- 该命令输出 `^ERROR` 行数 = 存量计数（一行可叠多条错误，见
  research.md R8；不与 pyrefly 汇总的 suppressed 数混用）。
- 版本口径：pyrefly 1.2.0（uv.lock 锁定），特性期间不升级
  （research.md R4）。

## 终态断言（批次 F 验收）

1. 上述命令输出 **0 条 ERROR**（存量 1064 → 0）。
2. `pyproject.toml` `[tool.pyrefly.errors]` **无任何条目**（9 → 0），
   表头注释更新为"豁免已退役"现状描述，不再引用已删除的存量数字。
3. `scripts/type_ratchet.py` `BASELINE` **为空**；空基线状态下脚本正常
   运行并通过（不因空表崩溃、不误报"全部低于基线"以外的异常）。
4. `KNOWN_RESIDUAL` 集合清空（或整段移除），相关注释同步。
5. `uv run python scripts/lint.py` 全绿（链路含 ruff → format →
   pyrefly → 棘轮 → 文档漂移）。
6. 拦截力恢复验证（负向测试）：在任意模块函数引入一条 bad-return
   （如返回值类型不符），默认 `pyrefly check`（无 `--error` 参数）即
   报错且 `lint.py` 非零退出；撤销引入。

## 中间态断言（每批次验收）

1. 全码强制检查总计数较上一批次下降，且**无任何错误码回升**
   （spec SC-006）。
2. 某错误码实测归零时，`BASELINE` 删该键、pyproject 删该行、门禁复跑
   全绿，三动作同批次完成（宪法 III，spec FR-003）。
3. `uv run pytest -m "not integration"` 全绿。

## 行为语义（棘轮脚本，改造前后一致）

- 基线只减不增：计数 > 基线 → 非零退出阻断；计数 < 基线 → 通过并
  提示下调；空基线 + 空输出 → 通过（终态）。
- 脚本自身不属于豁免对象：对它的修改同样过 ruff/pyrefly 门禁。

## 配置变更过程约束

- 每次基线下调/豁免移除与对应代码修复**同提交或同批次相邻提交**，
  提交说明注明错误码与前后计数（Conventional Commits，`fix`/`chore`/
  `refactor` 按改动性质）。
- `pyproject.toml` 表头行尾的 `# 存量 N` 注释随退役逐条删除，
  禁止残留陈旧数字。
