import os
import shutil
import subprocess
import sys

print("初始化开发环境中...")

current_file_dir = os.path.dirname(__file__)

# 检测 uv 是否可用，否则回退 pip
use_uv = shutil.which("uv") is not None

if use_uv:
    print("检测到 uv，使用 uv sync 安装依赖（含 dev 组）...")
    subprocess.check_call(["uv", "sync"], cwd=current_file_dir)
else:
    print("未检测到 uv，回退到 pip ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ruff", "pyrefly"])

# 初始化 Githooks：直接指向 .githooks 目录，源目录更新即时生效
print("初始化 GitHooks 中...")
subprocess.check_call(["git", "config", "core.hooksPath", ".githooks"], cwd=current_file_dir)

print("初始化开发环境完成")
print()
print("后续命令请使用 uv 前缀:")
print("  uv run python ...")
print("  uv run ruff check ./bilibili_api/")
print("  uv run ruff format ./bilibili_api/")
print("  uv run pyrefly check ./bilibili_api/")
print("  uv run pytest")
