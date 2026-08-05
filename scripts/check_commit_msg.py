"""Conventional Commits 提交信息兜底校验脚本。

本地 commit-msg 钩子依赖 install.py 设置 core.hooksPath 后才会生效，可能被跳过。
本脚本与 .githooks/commit-msg 共用同一校验正则、随仓库传播，在 CI 中仅对增量提交
做服务端兜底校验，防止非法格式的提交信息流入主干。

用法：
    # commit-msg 钩子兼容模式：校验消息文件首行
    python scripts/check_commit_msg.py <commit-msg-file>

    # 提交范围模式：仅校验 base..head 区间内的增量提交
    python scripts/check_commit_msg.py --range <base> <head>
"""

import re
import subprocess
import sys

# 与 .githooks/commit-msg 中的 VALID_MSG_PATTERN 保持一致，修改时须两边同步
VALID_MSG_PATTERN = r"^(build|chore|ci|docs|feat|fix|perf|refactor|release|revert|style|test|tests)(\(?.+\)?!?)?:\s.*$"


def is_valid(first_line: str) -> bool:
    """校验提交信息首行是否符合 Conventional Commits 格式。

    Args:
        first_line: 提交信息首行

    Returns:
        bool: 是否合法
    """
    return re.match(VALID_MSG_PATTERN, first_line) is not None


def check_msg_file(msg_file: str) -> int:
    """commit-msg 钩子兼容模式：校验消息文件首行。

    Args:
        msg_file: 提交信息文件路径

    Returns:
        int: 退出码，0 为通过，1 为校验失败
    """
    with open(msg_file, encoding="utf8") as f:
        first_line = f.readlines()[0]
    if not is_valid(first_line):
        print("Invalid format of commit message, please refer to: https://www.conventionalcommits.org/zh-hans/v1.0.0/")
        return 1
    return 0


def check_range(base: str, head: str) -> int:
    """提交范围模式：仅校验 base..head 区间内每个增量提交的信息首行。

    Args:
        base: 区间起点（不含），如 origin/dev
        head: 区间终点（含），如 HEAD

    Returns:
        int: 退出码，0 为全部通过，1 为存在非法提交信息
    """
    output = subprocess.check_output(
        ["git", "rev-list", "--reverse", f"{base}..{head}"],
        text=True,
        encoding="utf-8",
    )
    shas = output.split()
    failed: list[str] = []
    for sha in shas:
        message = subprocess.check_output(
            ["git", "log", "-1", "--format=%B", sha],
            text=True,
            encoding="utf-8",
        )
        first_line = message.splitlines()[0] if message.strip() else ""
        # 合并提交信息由平台生成，不适用 Conventional Commits 约定
        if first_line.startswith("Merge "):
            continue
        if not is_valid(first_line):
            failed.append(f"  {sha[:8]}: {first_line}")
    if failed:
        print("以下增量提交的提交信息不符合 Conventional Commits 格式：")
        print("\n".join(failed))
        print("请参考: https://www.conventionalcommits.org/zh-hans/v1.0.0/")
        return 1
    print(f"共校验 {len(shas)} 个增量提交，全部符合 Conventional Commits 格式")
    return 0


def main() -> int:
    """解析命令行参数并分派到对应校验模式。

    Returns:
        int: 进程退出码
    """
    args = sys.argv[1:]
    if args and args[0] == "--range":
        if len(args) != 3:
            print("用法: check_commit_msg.py --range <base> <head>")
            return 2
        return check_range(base=args[1], head=args[2])
    if len(args) == 1:
        return check_msg_file(args[0])
    print("用法: check_commit_msg.py <commit-msg-file> | --range <base> <head>")
    return 2


if __name__ == "__main__":
    sys.exit(main())
