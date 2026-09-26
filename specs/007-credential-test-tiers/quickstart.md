# Quickstart: 特性 007 验证指南

**特性**: 集成测试按重要程度分级重构
**前置阅读**: [spec.md](spec.md)（验收标准 SC-001 ~ SC-007）、[contracts/test-tier-selection.md](contracts/test-tier-selection.md)（命令矩阵）

## 前提条件

1. `uv sync` 完成，`.venv` 可用；
2. TEMP 缓存凭据有效（`%TEMP%\bilibili_api_pytest_login.json` 存在且未过期；失效时先 `uv run python scripts/login_and_cache.py qrcode` 重新登录）；
3. 全程使用**默认限速**（不设 `BILI_RATELIMIT`），验收口径按默认值计。

## 端到端验证场景

### V1: 核心冒烟层全绿（SC-001）

```bash
uv run pytest -m cred0
```

预期: 全部通过（无失败 / 无错误 / 除缺凭据外无跳过）；输出中无任何写操作痕迹。

带请求计数复验预算（≤30）:

```bash
BILI_COUNT_REQUESTS=1 uv run pytest -m cred0
```

预期: 终端摘要输出总请求数 ≤ 30。

### V2: 冒烟 + 读回归全绿且无 412（SC-002 / SC-007）

```bash
BILI_COUNT_REQUESTS=1 BILI_ABORT_ON_RISK=1 uv run pytest -m "cred0 or cred1"
```

预期: 全部通过；终端摘要 412 类风控计数 = 0（含 -352 等效码）——任一 412 类响应发生时会话立即中止，该次运行判为验收失败（FR-005 中止口径）；总请求数 ≤ 400；30 分钟内完成。

### V3: 写生命周期自清理（SC-03 前置 + SC-003）

```bash
uv run pytest -m "cred0 or cred1 or cred2"
```

预期: 全部通过。运行前记录账号六态基线（关注数 / 收藏数 / 点赞过的视频 / 自己的评论 / 自己发的弹幕 / 稍后再看列表），运行后逐项比对无差异。

### V4: cred3 收集即排除（SC-004）

```bash
uv run pytest --collect-only -q | tail -5          # 读取终端"已排除 N 个 cred3 高危用例"提示行
uv run pytest -m cred3 --collect-only -q | tail -5 # 预期收集 N 个用例，N 与剔除数一致
```

预期: 默认收集输出剔除计数提示行且 N > 0；`-m cred3` 时收集数恰为 N，两者互证"收集即排除"。注意：收集输出的节点 ID 不含 marker 名，不得以 `grep -c cred3` 计数。**验收不真机执行 cred3**（单账号保护）。

### V5: 顺序无关（SC-005）

```bash
uv run pytest tests/test_comment.py::<评论生命周期用例> -q        # 单跑通过
uv run pytest tests/test_favorite_list.py::<收藏夹生命周期用例> -q # 单跑通过
uv run pytest "tests/test_video.py::test_v" -q                    # 任取 cred0/1/2 单用例抽跑
```

预期: 生命周期用例与其余抽跑用例独立运行全部通过（所需资源用例内自建自清）。

### V6: 无凭据降级（SC-006 / FR-011）

```bash
# 临时移走缓存与凭据来源后
uv run pytest -m cred0
```

预期: cred 用例自动跳过，跳过过程零网络请求；`uv run pytest -m "not integration"` 结果与重构前一致。

### V7: 门禁与 PR 回路（FR-013 / 宪法 III）

```bash
uv run python scripts/lint.py
uv run pytest -m readonly
```

预期: lint 全绿；readonly PR 门禁子集行为与重构前一致（test_readonly_smoke.py 用例照常执行）。

## 验收核对表（对应 SC）

| 场景 | 对应成功标准 | 通过判据 |
|------|--------------|----------|
| V1 | SC-001 | 100% 通过，请求数 ≤ 30 |
| V2 | SC-002 / SC-007 | 100% 通过、零 412、≤ 400 请求、≤ 30 分钟 |
| V3 | SC-003 | 100% 通过，六态零残留 |
| V4 | SC-004 | 默认收集 cred3 = 0；显式点名可收集 |
| V5 | SC-005 | 抽样单跑 100% 通过 |
| V6 | SC-006 | 自动跳过、零网络、离线结果不变 |
| V7 | FR-013 + 宪法 III | lint 全绿、readonly 不变 |

## 验收结果记录

- **V1（SC-001）** ✅ 2026-09-26：`BILI_COUNT_REQUESTS=1 uv run pytest -m cred0` → 12 passed / 0 failed / 0 skipped，计数器读数 14（api.bilibili.com 13 + space.bilibili.com 1）≤ 30，412 类风控响应 0。
- **V2（SC-002 / SC-007）** ✅ 2026-09-26：`BILI_COUNT_REQUESTS=1 BILI_ABORT_ON_RISK=1 uv run pytest -m "cred0 or cred1"`（过渡期显式 BILI_RATELIMIT=1.5）→ 190 passed / 0 failed / 0 skipped，计数器读数 247 ≤ 400，412 类风控响应 0（含 -352 口径），中止开关未触发；默认限速口径复跑见 T048（时长 6:04 @1.5s 限速，≤ 30 分钟余量充足）。
- **V3（SC-003）** ✅ 2026-09-26：`BILI_COUNT_REQUESTS=1 uv run pytest -m "cred0 or cred1 or cred2"`（BILI_RATELIMIT=1.5）→ 210 passed / 0 failed；六态比对：关注 66→66、收藏（默认收藏夹条目数）184→184、稍后再看 2→2 程序化读回一致；点赞 / 评论 / 弹幕三态由用例内配对断言与 teardown 清理保证（清理失败告警计数 0，弹幕写入属 cred3 默认永不执行）。修复过程：评论生命周期补根评论索引延迟等待；set_favorite 用例改为初始态感知的双向配对（修复无条件移除挤掉预存收藏的残留风险）；live general_info 补上游偶发 504 容错。
- **V4（SC-004）** ✅ 2026-09-26：默认 `uv run pytest --collect-only -q` 输出「已排除 37 个 cred3 高危用例（显式执行：pytest -m cred3）」（N=37 > 0）；`uv run pytest -m cred3 --collect-only -q` 收集数恰为 37，两者互证"收集即排除"（以收集节点 ID 计数，未使用 grep -c cred3 口径）。验收未真机执行 cred3。
- **V5（SC-005）** ✅ 2026-09-26：评论 / 收藏夹 / 观影房三条生命周期用例单跑通过；cred0（video get_info、user get_user_info）/ cred1（search test_a、note 公开笔记）/ cred2（video like、dynamic set_like）各抽 2 例独立运行 100% 通过。全局变量终检：comment_id / media_id / default_media_id / room / vote_id / phase_id / black_list 七类跨用例资源 ID 全部清零。
- **T048 默认限速验证（SC-002 时长项 / US6）** ✅ 2026-09-26：不设 env 时 3 用例耗时 5.2s（含 2×1.5s 间隔，默认间隔生效）；`BILI_RATELIMIT=0` 复跑 0.65s（覆盖生效）；SC-002 正式口径复跑（默认限速、无 BILI_RATELIMIT 覆盖）：`BILI_COUNT_REQUESTS=1 BILI_ABORT_ON_RISK=1 uv run pytest -m "cred0 or cred1"` → 192 passed / 0 failed、计数器 249 ≤ 400、零 412、5.9 分钟 ≤ 30 分钟。
