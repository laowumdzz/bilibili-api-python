# Quickstart: 验证指南——清零 pyrefly 存量类型错误

**Feature**: 005-pyrefly-type-debt | **Date**: 2026-09-25

本指南给出可运行的验证场景，证明特性按 spec 交付。命令均在仓库根执行，
前置条件 `uv sync` 已完成。契约细节见 [contracts/gate-tooling.md](contracts/gate-tooling.md)
与 [contracts/public-api-compatibility.md](contracts/public-api-compatibility.md)；
台账概念见 [data-model.md](data-model.md)；根因与批次依据见
[research.md](research.md)。

## 场景 0：环境与口径就绪（任何批次前）

```bash
uv sync
uv run pyrefly --version        # 预期 1.2.0（uv.lock 锁定）
```

## 场景 1：批次 0 校准（特性第一个动作）

```bash
grep -n '"bad-argument-type"' scripts/type_ratchet.py   # 改前 69
```

- **操作**：基线 69 → 68（纯脚本编辑，无源码变更）。
- **预期**：`uv run python scripts/type_ratchet.py` 通过且不再提示
  bad-argument-type 有下调空间。

## 场景 2：任意中间批次验收（批次 1..N 通用）

以某模块清扫批次为例（假设该批次消除了 user.py 的存量）：

```bash
# 1) 同口径计数：总 ERROR 行数较上一批次下降，且逐码无回升
uv run pyrefly check ./bilibili_api/ \
  --error bad-argument-type,bad-assignment,bad-function-definition,bad-index,bad-override,bad-return,missing-attribute,not-iterable,unsupported-operation \
  --output-format min-text --color never | grep -c "^ERROR"

# 2) 全量门禁（ruff → format → tests/scripts 阻断 → pyrefly → 棘轮 → 文档漂移）
uv run python scripts/lint.py

# 3) 离线测试
uv run pytest -m "not integration"
```

- **预期**：三条命令分别给出"计数下降、无回升"、"全绿"、"全绿"。
- **若批次内有错误码归零**：另查 `pyproject.toml` 该豁免行已删、
  `scripts/type_ratchet.py` 该基线键已删（同批次成对，见
  [contracts/gate-tooling.md](contracts/gate-tooling.md) 中间态断言）。

## 场景 3：公共 API 兼容抽查（contracts 契约验证）

```bash
# 库可导入且核心公开符号签名未收窄（抽样）
uv run python - <<'EOF'
import inspect
from bilibili_api import video, user, live
from bilibili_api.utils.network import Credential
print(inspect.signature(video.Video.get_info))
print(inspect.signature(user.User.get_videos))
print(inspect.signature(live.LiveRoom.get_room_info))
EOF
```

- **预期**：正常打印；参数名/默认值与特性开始前一致（对照 git 历史抽查）。
- 离线测试全绿本身覆盖大部分运行时行为回归面。

## 场景 4：终态验收（批次 F 后，spec FR-010 / SC-001..006）

```bash
# 1) 强制全码检查 0 错误
uv run pyrefly check ./bilibili_api/ \
  --error bad-argument-type,bad-assignment,bad-function-definition,bad-index,bad-override,bad-return,missing-attribute,not-iterable,unsupported-operation \
  --output-format min-text --color never        # 预期 INFO 0 errors

# 2) 默认检查同样 0 错误（豁免表已清空）
uv run pyrefly check ./bilibili_api/            # 预期 0 errors

# 3) 豁免表与基线为空
grep -A3 '\[tool.pyrefly.errors\]' pyproject.toml    # 预期表下无条目行
grep -n 'BASELINE' scripts/type_ratchet.py           # 预期空字典

# 4) 全量门禁 + 离线测试
uv run python scripts/lint.py
uv run pytest -m "not integration"

# 5) 文档零漂移
uv run python scripts/doc_gen.py && git status --short docs/   # 预期无变更
```

## 场景 5：拦截力恢复（负向测试，终态后做一次）

```bash
# 临时在任意模块函数里返回一个与注解不符的值（如注解 dict 的函数 return 1）
# 然后运行：
uv run python scripts/lint.py        # 预期 pyrefly 段非零退出并指出文件行号
# 撤销临时改动后复跑，恢复全绿
```

- **预期**：曾豁免的类别（bad-return 等）如今默认拦截——这是
  spec User Story 1 的直接验证。

## 已知真 bug 的验证（research.md R1 表格，随所属批次）

- `channel_series.py:231`、`cheese.py:345`（漏 `await`）：修复提交后
  对应功能离线冒烟（如 `ChannelSeries.get_meta` 协程正确等待），
  修复与类型变更分属不同提交，可分别 `git log` 追溯。
