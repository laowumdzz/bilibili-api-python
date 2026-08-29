import shutil
import subprocess
import sys


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

# 独立非阻断步骤：将检查范围扩展到 tests/ 与 scripts/ 的预览（2026-08-05 存量约 129 处违规，
# 以 T201 print / I001 / F401 为主）；存量清零后再提升为阻断门禁，不与上述豁免债合并处理。
print("Running ruff check on tests/ & scripts/ (non-blocking) ...")
ret = run(["ruff", "check", "./tests/", "./scripts/"])
if ret != 0:
    print(f"[non-blocking] ruff check on tests/ & scripts/ exited with {ret}; gate continues.")

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
sys.exit(ret)
