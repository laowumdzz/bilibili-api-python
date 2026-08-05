# 重复代码重构对比报告

> 目标：将 `bilibili_api/` 重复代码率降至 **5% 以下**。
> 结果：**5.45% → 2.13%**，达成目标。

## 测量方法

- 工具：`pylint --disable=all --enable=duplicate-code --output-format=json`（默认相似度阈值，等价于 >80% 相似的连续代码块）
- 范围：`bilibili_api/` 全部源码，排除第三方 vendored 的 `danmaku2ass.py` 与 `tools/`
- 重复率 = 去重后重复行数 / 总代码行数
- 分析脚本：`temp/dup_analyze.py`

## 总体结果

| 指标 | 重构前（基线） | 重构后 | 变化 |
| --- | --- | --- | --- |
| 总代码行数 | 32470 | 32161 | -309 |
| 重复行数（去重后） | 1768 | 685 | **-1083** |
| 重复簇数量 | 40 | 23 | -17 |
| **重复率** | **5.45%** | **2.13%** | **-3.32 pp** |

## 重构批次明细

### 批次 1 — protobuf 弹幕解析（最大热点，消除约 500 行）

- 提交：`427ca59` `refactor(video,cheese): 提取弹幕 protobuf 解析为公共函数`
- 问题：`video.py` 与 `cheese.py` 各自实现了一份几乎相同的 protobuf 弹幕解析（`get_danmaku_view` 响应解析、`get_danmakus` 分段解析），两处各约 250 行。
- 方案：新建 `bilibili_api/utils/_danmaku_parse.py`，提供 `parse_danmaku_view()` / `parse_danmaku_segment()` 两个公共函数（取 `video.py` 的超集实现，兼容花式弹幕与 settings 字段），两个模块调用点简化为一行。异常包装差异保持在调用方。

### 批次 2 — article/note 节点类与图片加载（消除约 180 行）

- 提交：`54f7e06` `refactor(article,note,opus): 复用一致的节点类并提取图片加载公共函数`
- 问题：`note.py` 重复定义了 `article.py` 中的 Markdown/富文本节点类；`note.py` 与 `opus.py` 的 `get_images()` 逻辑一致。
- 方案：
  - `note.py` 直接复用 `article` 的 `Node` / `BoldNode` / `ColorNode` / `FontSizeNode` / `ImageNode`；保留存在行为差异的 `DelNode` / `UnderlineNode` / `TextNode` 独立实现。
  - `utils/picture.py` 新增 `load_pictures()`，`note` / `opus` 的 `get_images()` 复用。

### 批次 3 — Upos 分块上传（消除约 120 行）

- 提交：`205dab9` `refactor(video_uploader): 提取 Upos 分块并发上传与参数构建为公共函数`
- 问题：`utils/upos.py` 与 `video_uploader.py` 各自实现了分块上传参数构建、并发任务调度 + 失败重试、文件大小获取逻辑。
- 方案：`upos.py` 提取模块级公共函数 `build_chunk_upload_params()` 与 `upload_chunks_with_retry()`；`video_uploader.py` 通过闭包适配任务签名后复用；文件大小统一改用 `os.path.getsize`（`VideoUploaderPage` 保留 `cached_size` 缓存）。

### 批次 4 — 请求客户端基类辅助方法（消除约 150 行）

- 提交：`900c4db` `refactor(clients): 提取请求/响应日志与文件处理为基类公共方法`
- 问题：`AioHTTPClient` / `HTTPXClient` / `CurlCFFIClient` 三个客户端的 `request()` 中，REQUEST/RESPONSE 日志分发与文件打开/关闭逻辑完全重复。
- 方案：`BiliAPIClient`（`utils/_session.py`）基类新增 `_log_request()` / `_log_response()` / `_open_request_files()` / `_close_request_files()` 静态方法，三个客户端统一复用。

## 刻意保留的重复

以下重复经评估后**有意保留**，强行合并会破坏公共 API 语义或降低可读性：

| 位置 | 原因 |
| --- | --- |
| `audio_uploader` / `video_uploader` 的 `UploaderEvents` 枚举 | 事件集合本就不同，是刻意差异化的公共 API |
| 客户端静态 docstring | 历史决策（曾用运行时 `__doc__` 复制，后改回静态），且 `doc_gen.py` 依赖 |
| `note.py` 的 `DelNode` / `UnderlineNode` / `TextNode` | 与 `article` 版本存在 markdown 转义等行为差异 |
| 客户端 download/WS 日志 dispatch | 各客户端事件参数不同（如 curl_cffi 有 impersonate 头处理），提取后收益低、可读性差 |

## 验证结果

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 离线测试 | `uv run pytest -m "not integration"` | ✅ 31 passed |
| 只读集成测试 | `uv run pytest -m readonly` | ✅ 5 passed |
| 完整测试套件 | `uv run pytest` | ✅ **343 passed**（含全部集成用例，0 skip / 0 fail，耗时约 2 分钟） |
| ruff check + format | `uv run python scripts/lint.py` | ✅ `bilibili_api/` 全部通过 |
| pyrefly 类型检查 | 同上 | ✅ 0 errors |
| 提交信息规范 | git hook（Conventional Commits） | ✅ 4 个提交均通过校验 |

## 结论

重复代码率从 **5.45%** 降至 **2.13%**，超额完成 5% 目标；所有现有测试（离线 / 只读集成 / 完整集成）全部通过，静态检查零错误，公共 API 行为保持不变。
