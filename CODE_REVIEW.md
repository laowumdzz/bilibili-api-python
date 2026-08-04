# bilibili-api-python 代码审查报告

**审查日期:** 2026-08-04  
**代码量:** ~34,600 行 (bilibili_api/)  
**工具:** ruff (278 errors), 手动审查, 测试运行

---

## 一、致命 Bug (会导致运行时崩溃)

### 🔴 1. `_video_monitor.py` — `Video` 和 `iscoroutine` 未导入

**文件:** `bilibili_api/_video_monitor.py:96,147`

```python
self.__video = Video(bvid, aid, credential=credential)  # Video 未导入
self.__bvid = await bvid if iscoroutine(bvid) else bvid  # iscoroutine 未导入
```

`Video` 类和 `iscoroutine` 函数在使用前完全没有导入，一旦实例化 `VideoOnlineMonitor` 或调用 `.connect()` 就会 `NameError`。整个模块完全不可用。

**修复:** 添加 `from .video import Video` 和 `from asyncio import iscoroutine`。

---

### 🔴 2. `dynamic.py:864` — `jump_url` 在赋值前使用

**文件:** `bilibili_api/dynamic.py:860-866`

```python
if (
    module["major"][key].get("jump_url") is not None
    ...
):
    cover = module["major"][key].get("cover")
    if jump_url.startswith("//"):      # ← jump_url 未定义！
        jump_url = "https:" + module["major"][key].get("jump_url")
```

进入 `if` 块后直接使用 `jump_url`，但该变量从未在当前作用域中赋值。应为 `module["major"][key].get("jump_url")` 先赋值给 `jump_url` 再判断。

**修复:**
```python
jump_url = module["major"][key].get("jump_url")
if jump_url and jump_url.startswith("//"):
    jump_url = "https:" + jump_url
```

---

### 🔴 3. 多个文件引用未导入的异常类

| 文件 | 缺失导入 |
|------|---------|
| `utils/initial_state.py:76` | `NetworkException`, `ResponseCodeException` |
| `utils/short.py:30` | `NetworkException`, `ResponseCodeException` |
| `video.py:626,888` | `ResponseCodeException` |

这些 `except (NetworkException, ResponseCodeException)` 子句在触发时会抛出 `NameError`。

**修复:** 在对应文件添加 `from ..exceptions import NetworkException, ResponseCodeException`。

---

### 🔴 4. `live_area.py` — 测试引用不存在的 `LiveRoomOrder` 枚举

**文件:** `tests/test_live_area.py:11`

```python
order=live_area.LiveRoomOrder.NEW,
```

`live_area` 模块中不存在 `LiveRoomOrder` 类。docstring 中提到了 `LiveRoomOrder` 但实际未定义。测试必然失败。

**修复:** 在 `live_area.py` 中定义 `LiveRoomOrder` 枚举，或在测试中改用字符串。

---

### 🔴 5. `_video_monitor.py:96` — 缩进错误导致 `__init__` 部分逻辑丢失

**文件:** `bilibili_api/_video_monitor.py:106-115`

```python
        self.__video = Video(bvid, aid, credential=***  

        # 智能选择在 log 中展示的 ID。
        id_showed = None
        ...
            self.__page_index = page_index    # ← 这些行缩进在 if/else 内
            self.__tasks = []
```

`self.__page_index` 和 `self.__tasks` 的赋值被错误地缩进到了 `if not self.logger.handlers:` 条件块内部，当 logger 已有 handlers 时这两个属性不会被初始化，后续访问会 `AttributeError`。

---

## 二、严重隐患 (特定条件下触发)

### 🟠 6. `_api.py:367` — `except BaseException` 吞掉所有异常

**文件:** `bilibili_api/utils/_api.py:367`

```python
except ResponseCodeException as e:
    if e.code == -403 and self.wbi:
        recalculate_wbi()
        continue
    raise e
except BaseException:
    raise WbiRetryTimesExceedException()
```

任何非 `ResponseCodeException` 的异常（包括 `KeyboardInterrupt`、`SystemExit`、`CancelledError`、网络超时等）都会被错误地包装成 `WbiRetryTimesExceedException`，丢失原始异常上下文。这会让调试变成噩梦。

**修复:** 只捕获需要的异常类型，或至少 `except Exception`，并使用 `raise ... from err`。

---

### 🟠 7. 大量可变默认参数 (B006, 53 处)

**涉及文件:** `_video_download.py`, `bangumi.py`, `channel_series.py`, `cheese.py`, `clients/*.py`, `dynamic.py`, `interactive_video.py`, `_session.py`, `_credential.py` 等

```python
async def set_favorite(
    self, add_media_ids: list[int] = [], del_media_ids: list[int] = []
):
```

Python 中可变对象作为默认值会在所有调用间共享，如果函数内部修改了该列表，后续调用的默认值会发生变化。这是 Python 最经典的陷阱之一。

**修复:** 默认使用 `None`，函数内部初始化：
```python
def func(arg: list[int] | None = None):
    if arg is None:
        arg = []
```

---

### 🟠 8. `asyncio.get_event_loop()` 已弃用 (10 处)

**涉及文件:** `utils/sync.py`, `utils/_session.py`, `clients/AioHTTPClient.py`, `_video_monitor.py`

Python 3.10+ 中 `asyncio.get_event_loop()` 在没有运行中的事件循环时会发出 `DeprecationWarning`，Python 3.12+ 中直接报错。

**修复:** 使用 `asyncio.get_running_loop()` 或 `asyncio.new_event_loop()`。

---

### 🟠 9. `_video_monitor.py:182` 及其他 — 裸 `except:` (10 处)

**涉及文件:** `_video_monitor.py`, `article.py`, `live.py`, `tools/ivitools/player.py`

```python
try:
    data, flag = await self.__client.ws_recv(self.__ws)
except:  # ← 会捕获 KeyboardInterrupt, SystemExit 等
    self.logger.warning("连接被异常断开")
```

裸 `except:` 会静默吞掉 `KeyboardInterrupt` 和 `SystemExit`，导致程序无法正常中断。

**修复:** 使用 `except Exception:`。

---

### 🟠 10. `_video_monitor.py` `__unpack` 方法存在缓冲区解析 bug

**文件:** `bilibili_api/_video_monitor.py:300-322`

```python
region_header = struct.unpack(">IIII", data[:16])   # 总是取前 16 字节
region_data = data[offset:offset + region_header[0]]  # offset 初始为 0
real_data.append({
    "data": json.loads(
        region_data[offset + 18 : offset + 18 + (region_header[0] - 16)]
    ),
})
offset += region_header[0]
```

`struct.unpack(">IIII", data[:16])` 在循环中始终读取 `data[:16]` 而不是 `data[offset:offset+16]`，这意味着第二个及后续数据包的 header 解析是错误的。此外 `region_data` 的切片范围 `offset + 18` 在第二次循环时会越界。

---

### 🟠 11. `danmaku2ass.py` — `_()` 函数未定义 (50 处 F821)

**文件:** `bilibili_api/utils/danmaku2ass.py`

`gettext.install()` 在模块顶层调用，本应将 `_` 绑定到 builtins。但在某些运行环境中（如被 `import` 而非直接运行时），`sys.argv[0]` 为空字符串导致 locale 路径错误，`_` 不会被正确注入。

**修复:** 显式定义 `_ = gettext.gettext` 或使用 `from gettext import gettext as _`。

---

### 🟠 12. `cheese.py:320,555` — 异常链丢失

```python
except Exception as e:
    raise NetworkException(-1, str(e))  # 应为 raise ... from e
```

丢失了原始 traceback，调试困难。共 14 处 `B904`。

---

## 三、代码质量问题

### 🟡 13. 未使用的导入和变量 (25 F401 + 11 F841)

- `_video_download.py`: `field`, `Optional`, `URL` 导入未使用
- `_video_monitor.py`: `Optional`, `get_api` 导入未使用
- `dynamic.py:906-907`: `width`, `height` 赋值后未使用
- `opus.py:166-167`: 同上
- `user.py:1462`: `resp` 赋值后未使用
- `danmaku2ass.py:359`: `NiconicoColorMap` 定义后未使用

---

### 🟡 14. `== True` 比较 (6 处 E712)

**文件:** `manga.py:390`, `note.py:338,342,346,350`

```python
if status == True:           # 应为 if status:
if field["attributes"].get("bold") == True:  # 应为 if ...get("bold"):
```

---

### 🟡 15. `type()` 比较而非 `isinstance()` (4 处 E721)

**文件:** `article.py:290`, `note.py:222`

```python
if type(e) == element.NavigableString:   # 应为 isinstance(e, ...)
if type(line["insert"]) == dict:
```

---

### 🟡 16. `lstrip`/`rstrip` 用于多字符字符串 (5 处 B005)

**文件:** `game.py:226,245`, `interactive_video.py:884`, `opus.py:170`

```python
wiki_page_title.lstrip("https://wiki.biligame.com/wiki/")  # lstrip 按字符集删除，不是删除前缀！
prop.lstrip("WIKI域名=")  # 同上
```

`lstrip("https://...")` 会删除开头所有属于该字符集的字符（h, t, p, s, :, /, w, i, k, i...），而不是删除整个前缀字符串。这是一个非常容易误解的 API。

**修复:** 使用 `str.removeprefix()` (Python 3.9+)。

---

### 🟡 17. `UP036` — 过时的版本检查

**文件:** `danmaku2ass.py:31`

```python
if sys.version_info < (3,):
    raise RuntimeError("at least Python 3.0 is required")
```

项目要求 Python >= 3.10，这个检查完全无意义。

---

### 🟡 18. `__init__.py:125` — 循环变量名遮蔽导入 (F402)

```python
for module, client, settings in ALL_PROVIDED_CLIENTS[::-1:]:
    #                  ^^^^^^ 遮蔽了前面 import 的 client 模块
```

虽然此处逻辑上不影响运行（前面的 `client` 导入在此之后未使用），但容易引发混淆。

---

### 🟡 19. 测试框架不支持 pytest

现有测试通过 `python -m tests -m <module>` 运行，测试函数是普通 `async def` 而非 `pytest.mark.asyncio`。pytest 收集时会跳过这些异步测试。这限制了 CI/CD 的兼容性。

---

## 四、测试结果

### 不需要 Cookie 的测试运行结果

| 测试模块 | 结果 |
|---------|------|
| `test_article_category` | ✅ 5/5 passed |
| `test_cheese` | ✅ 3/3 passed |
| `test_client` | ✅ 1/1 passed |
| `test_emoji` | ✅ 1/1 passed |
| `test_festival` | ✅ 1/1 passed |
| `test_game` | ✅ 5/5 passed |
| `test_hot` | ✅ 5/5 passed |
| `test_initial_state` | ✅ 2/2 passed |
| `test_live_area` | ❌ 0/1 passed — `LiveRoomOrder` 不存在 |
| `test_video_uploader` | ✅ 1/1 passed |
| `test_video_zone` | ⚠️ 7/8 passed — `get_zone_new_videos(tid=3)` 返回 -404（API 可能已变更） |

**总计:** 31 passed, 2 failed (共 11 个无 cookie 测试模块)

需要 cookie 的测试模块 (26 个) 未运行。

---

## 五、优化建议

1. **修复致命 bug 后建立 CI** — 当前代码在 `_video_monitor.py` 和 `dynamic.py` 中有完全不可用的路径，说明缺少足够的集成测试覆盖。

2. **统一异常处理** — `except BaseException` 和裸 `except:` 应全部替换为精确的异常类型 + `raise ... from err`。

3. **迁移到 `asyncio.get_running_loop()`** — 为 Python 3.12+ 兼容做准备。

4. **使用 `frozenset` 或 `None` 哨兵** — 替代所有可变默认参数。

5. **`danmaku2ass.py` 考虑独立维护** — 这是第三方 fork (m13253/danmaku2ass)，代码风格与项目其余部分完全不同，存在大量 C 风格 printf 格式化和 gettext 用法。考虑将其作为独立依赖或重写关键函数。

6. **`_video_monitor.py` `__unpack` 需要完整重写** — 当前缓冲区解析逻辑在多包场景下是错误的。

7. **type hints 不完整** — 大量 `dict` 无泛型参数，建议统一使用 `dict[str, Any]` 等精确类型。

8. **考虑引入 `mypy`/`pyrefly` 到 CI** — pyproject.toml 已配置 pyrefly 但未实际运行，50 个 F821 (undefined name) 本应在类型检查阶段就被发现。

---

## 严重程度统计

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 致命 | 5 | 运行时立即崩溃 |
| 🟠 严重 | 7 | 特定条件下触发，影响调试或功能 |
| 🟡 质量 | 7 | 代码可运行但存在隐患 |
| **ruff 总计** | **278** | 含 50 个未定义名称、53 个可变默认参数等 |
