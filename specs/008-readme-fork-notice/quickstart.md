# Quickstart: 验收实操指南

**Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/readme-content.md](./contracts/readme-content.md)

README 改造完成后，按以下场景端到端验证。V1–V3、V6 为本地可完成的核心验收（无网络依赖，git bash / uv 环境即可）；V4–V5 为实操验证，需要网络与干净环境。对应用户故事：V1→US1，V2/V3/V4→US2，V5→US3。

## 前置

- 本仓库工作副本（`main` 分支），`uv` 可用。
- 校验脚本均以仓库根为工作目录。

## V1 注记逐字校验（对应 SC-001 / C1）

```bash
grep -cF "本项目Fork自https://github.com/nemo2011/bilibili-api的commit SHA为027563d2fe7604967242986aac51d693c905的分支并由AI维护" README.md
```

**预期**: 输出 ≥ 1（精确固定字符串匹配，`-F` 禁正则）。同时人工确认注记位于首屏（标题/徽章区之后、首个 `#` 章节之前或紧邻处）。

## V2 归属三态清点（对应 SC-002 / C3）

```bash
grep -noE "https?://[^ )\"]+|img\.shields\.io[^ )\"]+" README.md
```

**预期**: 逐条核对输出与 [data-model.md](./data-model.md) 实例清单（E01–E32）：每条归入 SELF / UPSTREAM_LABELED / REMOVED 之一；REMOVED 项做精确字符串零命中复核：

```bash
grep -cF "pypi.org/project/bilibili-api" README.md        # 预期 0
grep -cF "nemo2011/bilibili-api/stargazers" README.md     # 预期 0
grep -cF "star-history.com" README.md                     # 预期 0
grep -cF "raw.githubusercontent.com/Nemo2011" README.md   # 预期 0
```

剩余 nemo2011 引用必须全部伴随"上游"语义标注（人工目检）。

## V3 相对路径与渲染（对应 C7）

```bash
ls design/logo.png LICENSE docs/CHANGELOGS.md 2>/dev/null; ls docs | head -3
```

**预期**: `design/logo.png`、`LICENSE`、`docs/` 均存在。GitHub 页面目检：徽章渲染为图标非死链、脚注可跳转、注记无乱码（中英文与 SHA 完整）。

## V4 干净环境安装 + 示例（对应 SC-003 / C4 / US2）

```bash
python -m venv /tmp/bili-readme-check && source /tmp/bili-readme-check/Scripts/activate  # Windows git bash
pip install "git+https://github.com/laowumdzz/bilibili-api-python.git@main"
python -c "from bilibili_api import video, Credential, select_client, request_settings; print('imports ok')"
```

再按 README"快速上手"章节**原样**运行视频信息示例（`video.Video(bvid=...)` → `await v.get_info()`）。

**预期**: 安装成功且装的是本仓库代码（`pip show bilibili-api-python` 的版本与 `BILIBILI_API_VERSION` 一致）；示例输出视频信息 JSON。无网环境可降级为：`pip download` 离线核验 Release 资产存在 + 本地 `uv build` 产物安装后跑离线导入检查。

## V5 开发工作流实操（对应 SC-004 / C5 / US3）

按 README 开发章节**原样**执行：

```bash
uv sync
uv run python install.py
uv run python scripts/lint.py
uv run pytest -m "not integration"
```

**预期**: 环境就绪、Git Hooks 初始化、lint 门禁全绿、离线测试通过——README 所写命令与项目实态零偏差。

## V6 门禁回归（实现完成后必跑）

```bash
uv run python scripts/lint.py
```

**预期**: 全绿。README 不在 doc_gen 生成域，预期零影响；若门禁因本特性报错即为阻断缺陷。

## 遗留清单（范围外，验收时知会维护者）

见 [research.md](./research.md) 末节：`.github/CONTRIBUTING.md` 上游遗留重写、`docs/index.html` docsify 配置迁移、AGENTS.md 仓库地址与 git remote 漂移确认。
