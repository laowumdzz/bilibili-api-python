from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas: list[tuple[str, str]] = collect_data_files("bilibili_api")
# 包内功能子模块为惰性导入（PEP 562），静态分析无法追踪，需显式收集全部子模块
hiddenimports: list[str] = collect_submodules("bilibili_api")
