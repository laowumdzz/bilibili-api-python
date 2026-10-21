import glob
import json
import os
import shutil
import subprocess
import sys

# doc_gen 读取 mypy 的 JSON 缓存（.data.json）；mypy 1.19+ 已改为 SQLite 缓存，
# 必须锁定仍生成 JSON 格式的 1.18.x，否则文档漂移门禁无法运行。
# stubgen（随 mypy 提供）负责写入根包缓存条目，普通 mypy check 只写子包。
MYPY_CACHE_SPEC = "mypy==1.18.2"


# 优先用 uv run（自动使用 .venv），否则直接调用当前 python
def run(cmd: list[str]) -> int:
    if shutil.which("uv"):
        return subprocess.call(["uv", "run", *cmd])
    return subprocess.call([sys.executable, "-m", *cmd[0:1], *cmd[1:]])


print("Running ruff check ...")
ret = run(["ruff", "check", "./bilibili_api/"])
if ret != 0:
    sys.exit(ret)

print("Running ruff format --check ...")
ret = run(["ruff", "format", "--check", "./bilibili_api/"])
if ret != 0:
    sys.exit(ret)

# 阻断步骤：检查范围扩展到 tests/ 与 scripts/（2026-08-05 存量约 129 处违规已于后续清零，
# 由非阻断预览升级为阻断门禁）；install.py / scripts 下四个脚本的 T201 豁免在 pyproject 中有意保留。
print("Running ruff check on tests/ & scripts/ ...")
ret = run(["ruff", "check", "./tests/", "./scripts/"])
if ret != 0:
    sys.exit(ret)

print("Running pyrefly check ...")
ret = run(["pyrefly", "check", "./bilibili_api/"])
if ret != 0:
    sys.exit(ret)

# 豁免错误码存量棘轮（2026-08-29 引入）：[tool.pyrefly.errors] 豁免类别的存量计数只减不增，
# 新增类型错误在此被阻断；存量清零后从豁免表与脚本基线中移除对应错误码。
print("Running pyrefly type ratchet check ...")
if shutil.which("uv"):
    ret = subprocess.call(["uv", "run", "python", "scripts/type_ratchet.py"])
else:
    ret = subprocess.call([sys.executable, "scripts/type_ratchet.py"])
if ret != 0:
    sys.exit(ret)

# 文档漂移校验（2026-08-30 引入；2026-10-21 拆出缓存分支）：
# doc_gen 输出经两轮哈希比对确认确定性（无时间戳等非稳定内容；输出编码已显式 pin 为 UTF-8，
# 不受运行环境 locale 影响），重新运行 doc_gen 后以 git 检测 docs/modules/
# （doc_gen 的唯一输出目录，手写文档不受影响）是否与源码漂移。
# docstring 级漂移由 doc_gen 运行时导入源模块捕获，不依赖缓存新鲜度，每次都会比对；
# 公开符号级漂移依赖 .mypy_cache/<Python 版本>/ 的符号清单是否最新。
# 缓存缺失时用固定版本 mypy 的 stubgen 重建（见 MYPY_CACHE_SPEC），重建失败则明确失败
# 并给出重建命令，而不是静默跳过；缓存落后于源码时默认仅提示，DOCS_DRIFT_STRICT=1 时升级为失败。
print("Running docs drift check ...")
mypy_cache_dir = os.path.join(".mypy_cache", f"{sys.version_info.major}.{sys.version_info.minor}", "bilibili_api")
cache_ready = os.path.isfile(os.path.join(mypy_cache_dir, "__init__.data.json"))
if not cache_ready:
    print(f"mypy 缓存缺失（{mypy_cache_dir}），正在用 {MYPY_CACHE_SPEC} 的 stubgen 重建 ...")
    stubgen_args = ["stubgen", "bilibili_api", "-o", ".doc_cache/", "--include-docstrings"]
    if shutil.which("uv"):
        cache_build_cmd = ["uv", "run", "--with", MYPY_CACHE_SPEC, *stubgen_args]
    else:
        cache_build_cmd = stubgen_args
    try:
        cache_build = subprocess.run(cache_build_cmd, capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        print("错误: 未找到 uv 或 stubgen，无法重建 mypy 缓存。请安装 uv 后重试。")
        sys.exit(1)
    cache_ready = os.path.isfile(os.path.join(mypy_cache_dir, "__init__.data.json"))
    if not cache_ready:
        print(cache_build.stdout)
        print(cache_build.stderr)
        print(
            "错误: mypy 缓存重建失败，文档漂移校验无法运行。\n"
            "请手工执行（stubgen 会写入 doc_gen 所需的 JSON 缓存）：\n"
            f'  uv run --with "{MYPY_CACHE_SPEC}" stubgen bilibili_api -o .doc_cache/ --include-docstrings\n'
            f"然后确认 {mypy_cache_dir}/__init__.data.json 存在。"
        )
        sys.exit(1)
    if cache_build.returncode != 0:
        print(f"注意: stubgen 以退出码 {cache_build.returncode} 结束，但缓存已生成。")
    print(f"mypy 缓存已生成: {mypy_cache_dir}")

# 缓存新鲜度校验：doc_gen 的公开符号清单来自 mypy 缓存，缓存落后于源码时
# 新增/删除公开符号的漂移将无法检出（docstring 级漂移不受影响）。
stale: list[str] = []
project_src = os.path.normcase(os.path.abspath("bilibili_api"))
for meta_path in glob.glob(os.path.join(mypy_cache_dir, "**", "*.meta.json"), recursive=True):
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        continue
    src = meta.get("path")
    data_mtime = meta.get("data_mtime")
    if not src or not isinstance(data_mtime, (int, float)) or not os.path.isfile(src):
        continue
    # 仅校验本项目源码的缓存条目（缓存中可能残留其他环境的绝对路径）
    if not os.path.normcase(os.path.abspath(src)).startswith(project_src + os.sep):
        continue
    # 2 秒容差：规避文件系统时间戳粒度导致的误报
    if os.path.getmtime(src) - data_mtime > 2:
        stale.append(src)
if stale:
    print(
        f"注意: mypy 缓存落后于 {len(stale)} 个源文件（如 {stale[0]}），"
        "本次校验仅覆盖 docstring 级漂移，公开符号级漂移可能漏检"
    )
    if os.environ.get("DOCS_DRIFT_STRICT") == "1":
        print(
            "DOCS_DRIFT_STRICT=1：缓存陈旧即视为失败，请先执行 "
            f'uv run --with "{MYPY_CACHE_SPEC}" stubgen bilibili_api -o .doc_cache/ '
            "--include-docstrings 重建缓存后重试"
        )
        sys.exit(1)
# 仅比对 doc_gen 的输出目录 docs/modules/，避免误伤手写文档；
# 先快照运行 doc_gen 前的脏状态，只将「重新生成新增」的脏条目判为漂移，
# 预先存在的未提交变更不阻断（doc_gen 会覆盖 modules 下同名文件，无法归因）。
# git status --porcelain 比 git diff --exit-code 覆盖更全：含已暂存修改与新增未跟踪文件
before = subprocess.run(
    ["git", "status", "--porcelain", "--", "docs/modules/"],
    capture_output=True,
    text=True,
    errors="replace",
)
if before.returncode != 0:
    print(before.stderr)
    sys.exit(before.returncode)
pre_existing = set(before.stdout.splitlines())
# doc_gen 的日志为逐符号 INFO 输出（千余行），仅失败时回放便于定位
if shutil.which("uv"):
    doc_gen = subprocess.run(
        ["uv", "run", "python", "scripts/doc_gen.py"],
        capture_output=True,
        text=True,
        errors="replace",
    )
else:
    doc_gen = subprocess.run(
        [sys.executable, "scripts/doc_gen.py"],
        capture_output=True,
        text=True,
        errors="replace",
    )
if doc_gen.returncode != 0:
    print(doc_gen.stdout)
    print(doc_gen.stderr)
    sys.exit(doc_gen.returncode)
after = subprocess.run(
    ["git", "status", "--porcelain", "--", "docs/modules/"],
    capture_output=True,
    text=True,
    errors="replace",
)
if after.returncode != 0:
    print(after.stderr)
    sys.exit(after.returncode)
new_drift = [line for line in after.stdout.splitlines() if line not in pre_existing]
if pre_existing:
    print(f"注意: docs/modules/ 存在 {len(pre_existing)} 条运行前已有的未提交变更，不参与漂移判定")
if new_drift:
    print("文档漂移：重新生成 docs/modules/ 后出现新的未提交变更（已按当前代码重新生成到工作区）：")
    print("\n".join(new_drift))
    print("请检查上述变更并提交（docs/modules/ 为自动生成文档，禁止手改），或还原后重试。")
    sys.exit(1)
print("docs/modules/ 无漂移。")
