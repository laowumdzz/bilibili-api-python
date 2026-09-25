"""pyrefly 豁免错误码存量棘轮校验：存量只减不增。

背景：`pyproject.toml` 的 `[tool.pyrefly.errors]` 对一批上游存量类型错误做了
豁免（2026-08-06 审计），豁免类别中的新增类型错误不会被默认门禁拦截。本脚本
强制启用全部豁免错误码重跑类型检查，将各错误码计数与冻结基线对比：

- 计数高于基线 -> 判定为新增类型错误，退出码非零，阻断门禁；
- 计数低于基线 -> 提示同步下调脚本中的基线（基线只允许下调，不允许上调）。

基线冻结于 2026-08-29（测量方式与本脚本一致：
`pyrefly check ./bilibili_api/ --error <豁免码列表> --output-format min-text`）。
修复存量错误后，请仅向下更新基线；某错误码基线归零后，应从
`pyproject.toml` 豁免表中移除该条目并从本脚本基线中删除，恢复默认启用。
"""

from pathlib import Path
import re
import shutil
import subprocess
import sys

# 仓库根目录（本脚本位于 scripts/ 下），避免依赖调用方的工作目录
REPO_ROOT = Path(__file__).resolve().parent.parent

# 与 [tool.pyrefly.errors] 豁免表一一对应的存量基线（只减不增）
BASELINE: dict[str, int] = {
    "bad-argument-type": 66,
    "bad-assignment": 45,
    "bad-function-definition": 14,
    "bad-index": 223,
    "bad-override": 20,
    "bad-return": 376,
    "missing-attribute": 34,
    "not-iterable": 13,
    "unsupported-operation": 172,
}

# 非豁免表内、但在强制检查中仍会现身的错误码：一律视为异常并阻断（曾经的
# 残留码 bad-override-mutable-attribute / bad-override-param-name 已于
# 2026-09 特性 005 中修复归零，不再对冲豁免）。

# min-text 输出中每条错误的首行形如：
# ERROR path:line:col-range: message [error-code]
ERROR_LINE = re.compile(r"^ERROR .+\[([a-z][a-z\-]*)\]\s*$")


def run_pyrefly() -> tuple[int, str]:
    """以强制启用全部豁免错误码的方式运行 pyrefly，返回（进程返回码, min-text 输出）。"""
    codes = ",".join(sorted(BASELINE))
    cmd = [
        "pyrefly",
        "check",
        str(REPO_ROOT / "bilibili_api"),
        "--error",
        codes,
        "--output-format",
        "min-text",
        "--color",
        "never",
    ]
    if shutil.which("uv"):
        proc = subprocess.run(["uv", "run", *cmd], capture_output=True, text=True)
    else:
        proc = subprocess.run([sys.executable, "-m", *cmd], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def collect_error_lines(output: str) -> dict[str, list[str]]:
    """按错误码收集输出中的错误行（保留含文件路径与行号的原始行）。"""
    lines: dict[str, list[str]] = {}
    for line in output.splitlines():
        m = ERROR_LINE.match(line)
        if m:
            lines.setdefault(m.group(1), []).append(line)
    return lines


def main() -> int:
    returncode, output = run_pyrefly()
    error_lines = collect_error_lines(output)
    counts = {code: len(lines) for code, lines in error_lines.items()}

    # pyrefly 报错时返回码为 1，因此仅当“返回码非零且没有任何可解析的错误行”时，
    # 才判定为检查本身未完成（命令缺失、运行异常等）：此时零计数不代表存量清零，
    # 不能按“全部低于基线”放行，打印原始输出并以非零退出码阻断。
    if returncode != 0 and not counts:
        print(f"类型存量棘轮校验失败：pyrefly 检查未正常完成（返回码 {returncode}），原始输出如下：")
        print(output.strip() or "（无输出）")
        return 1

    regressions: list[str] = []
    regressed_codes: list[str] = []
    improvements: list[str] = []
    for code in sorted(BASELINE):
        actual = counts.get(code, 0)
        limit = BASELINE[code]
        if actual > limit:
            regressions.append(f"  {code}: 存量 {actual} > 基线 {limit}")
            regressed_codes.append(code)
        elif actual < limit:
            improvements.append(f"  {code}: 存量 {actual} < 基线 {limit}，请下调 BASELINE")
    unexpected = sorted(code for code in counts if code not in BASELINE)

    if regressions:
        print("类型存量棘轮校验失败：以下豁免错误码出现新增类型错误（存量只减不增）：")
        print("\n".join(regressions))
        print("回归错误码对应的错误行（含文件路径与行号）：")
        for code in regressed_codes:
            for line in error_lines[code]:
                print(f"  {line}")
        print("请修复新增的类型错误；基线不允许上调。")
        return 1
    if unexpected:
        # 基线之外的错误码出现报错：可能是豁免表与本脚本失同步，或新引入的错误落在豁免类别，
        # 一律阻断并要求人工核对，避免豁免缺口扩大。
        print("类型存量棘轮校验失败：检测到基线之外的错误码报错，请核对豁免表与本脚本基线：")
        for code in unexpected:
            print(f"  {code}: {counts[code]}")
        return 1
    if improvements:
        print("以下错误码存量已低于基线，请下调 scripts/type_ratchet.py 的 BASELINE（只减不增）：")
        print("\n".join(improvements))
    print(f"类型存量棘轮校验通过：{len(BASELINE)} 个豁免错误码存量均未超过基线。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
