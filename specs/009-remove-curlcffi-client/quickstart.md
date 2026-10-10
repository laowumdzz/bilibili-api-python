# Phase 1 Quickstart: 验收实操指南

**Feature**: 009-remove-curlcffi-client | **Date**: 2026-10-11

按顺序执行以下验证场景，全部通过即满足 spec 的 SC-001 ~ SC-005（SC-005 为定性项，由 §4 报错文案与 §6 文档核对共同覆盖）。契约细节见 [contracts/client-selection.md](./contracts/client-selection.md)。

## 前置条件

- uv 可用（`uv sync` 前无须预装任何客户端库）。
- 本机已有 `.venv`（真机冒烟场景需要 `.bilibili.cookie` 或 BILI_* 凭据；缺凭据时 §5 自动 skip，不阻塞其余场景）。

## 1. 依赖清洁（SC-003 前置）

```bash
uv sync
uv pip list | grep -i curl    # 期望：无输出（curl-cffi 从环境消失）
grep -n "curl" pyproject.toml requirements.txt    # 期望：无输出
```

## 2. 离线全量（SC-004 主体）

```bash
uv run pytest -m "not integration"
```

期望：全绿。含——保留的 aiohttp/httpx 超时语义与 WS 泄漏用例、新增 `tests/test_offline_client_selection.py` 三场景（清单契约 / 回退与默认选择 / 干净移除）；终端无 curl 相关 skip（`HAS_CURL_CFFI` 条件分支应已不存在）。

## 3. 运行时行为抽查（契约 §1–§4）

```bash
uv run python -c "
import importlib
from bilibili_api.utils._session import select_client, get_registered_clients, get_client
from bilibili_api import get_selected_client

print('已注册:', sorted(get_registered_clients()))          # 期望 ['aiohttp', 'httpx']（含顺序无关）
print('默认选中:', get_selected_client()[0])                # 期望 'aiohttp'
try:
    select_client('curl_cffi')
except Exception as e:
    print(type(e).__name__, e)   # 期望 ArgsException，消息含'当前已注册的客户端：aiohttp, httpx'
try:
    importlib.import_module('bilibili_api.clients.CurlCFFIClient')
except ModuleNotFoundError:
    print('模块已干净移除')      # 期望输出此行
"
```

期望输出与注释一致；`get_client()` 在两客户端齐备时返回 AioHTTPClient 实例（不报"尚未安装"）。

## 4. 足迹检索（SC-003）

机械命中检索（豁免写法不依赖 `./` 路径前缀与路径分隔符方向：`grep -rn` 输出行首首个冒号之前为路径段，`^[^:]*` 将豁免锚定在路径段内、不误伤内容命中；豁免片段一律不含路径分隔符——Windows Git Bash 的 `grep -r` 输出反斜杠路径，实测其括号类 `[\\/]` 无法匹配反斜杠，故弃用目录前缀式写法）：

```bash
grep -rni "curl_cffi\|CurlCFFI\|curl-cffi" \
  --include="*.py" --include="*.toml" --include="*.md" --include="*.txt" --include="*.json" . \
  | grep -v "^[^:]*bilibili-api-registry" \
  | grep -v "^[^:]*v17\.md\|^[^:]*v18\.md\|^[^:]*UNRELEASED\.md" \
  | grep -v "^[^:]*REFACTORING\.spec\.md" \
  | grep -v "^[^:]*specs[^:]*00[12589]-" \
  | grep -v "^[^:]*test_offline_client_selection\.py" \
  | grep -v "^[^:]*request_client\.md" \
  | grep -v "^[^:]*constitution\.md"
```

**判定标准**：有效引用 = 将 CurlCFFI 描述为可用客户端的表述；命令输出为机械命中，逐条人工分类后计数。以下四类合规语境已在命令中按路径豁免（与 data-model §6 豁免清单保持一致）：

- `CHANGELOGS/UNRELEASED.md` — 移除记录本体（影响面与迁移指引）；
- `docs/request_client.md` — 自定义客户端教程节（research R5 裁决的"第三方自定义接入示例"教学语境）；豁免按文件整体放行，若命中超出教程节范围须人工重判；
- `tests/test_offline_client_selection.py` — FR-007 移除契约锚定断言（断言 CurlCFFI 不可用）；
- `.specify/memory/constitution.md` — 头部 Sync Impact Report 的 from→to 修订记载。

期望：无输出（0 有效引用）。其余文件出现输出时按上述判定标准逐条人工分类；若 `uv.lock` 或 `docs/modules/client.md` 出现，说明 SYNC/REGEN 步骤未执行。

## 5. 真机冒烟（SC-001 / SC-002；需凭据）

```bash
uv run pytest -m cred0
uv run pytest -m readonly
```

期望：全绿（缺凭据自动 skip 不算失败）。请求计数器（`BILI_COUNT_REQUESTS=1`）下的域名汇总行为不变——计数器挂钩仍覆盖两个内置客户端。

**可选——最小环境只读冒烟**（对应 SC-001 的真实单客户端环境验证；非常规验收门槛，环境突变自担）：

```bash
uv pip uninstall aiohttp
uv run pytest -m readonly        # 期望：全绿或凭据缺失 skip；此环境默认选中 httpx
uv sync                          # 立即复装 aiohttp，恢复常规环境
uv run pytest -m cred0           # 复装后复跑，确认回到 aiohttp 默认路径
```

仅在凭据可用且愿意承受临时环境变更时执行；"仅装 aiohttp" 分支由常规环境（aiohttp 优先选中）天然覆盖，"全部缺失"分支由离线打桩测试覆盖。

## 6. 文档与治理一致性（SC-003 / SC-005 定性项）

- `README.md` 与 `docs/README.md` 镜像内容逐段一致，优先级表述为 aiohttp > httpx，无 impersonate 段。
- `docs/request_client.md`：对比表仅两行；自定义客户端教程将 curl_cffi 标注为"第三方自定义接入示例"。
- `AGENTS.md` 6 处、`.github/ISSUE_TEMPLATE/troubleshooting.md` 1 处已同步。
- 宪法原则 I 优先级链为 `aiohttp > httpx`，版本 1.0.2，头部有 Sync Impact Report。
- `CHANGELOGS/` 新版本节含影响面与迁移指引（对应契约 §5 三行表）。

## 7. 门禁（SC-004 收口）

```bash
uv run python scripts/lint.py
```

期望：全绿。文档漂移校验会比对 `docs/modules/client.md` 与源码——若忘跑 `doc_gen.py`，此步必红。

## 故障排查

| 现象 | 原因 | 处置 |
|------|------|------|
| §2 有 `CurlCFFIClient` 导入错误 | conftest 包装清单或测试文件残留 | 检查 data-model T1/T2/T3 |
| §3 默认选中为 `httpx` | aiohttp 未安装（`uv sync` 未执行或环境损坏） | 重跑 `uv sync` |
| §4 命中 `uv.lock` | 改了 pyproject 后未 `uv sync` | 重跑 `uv sync` |
| §7 文档漂移红 | 删模块后未重生成文档 | `uv run python scripts/doc_gen.py` 后入库 |
