# Research: pytest 临时登录凭据（--login）

**Date**: 2026-08-31 | **Status**: 全部待定项已决议

## D1. `--login` 参数的挂载位置

- **Decision**: 在 `tests/conftest.py` 中实现 `pytest_addoption`，注册 `--login` 选项（`choices` 约束 + 手工校验非法值抛 `pytest.UsageError`）。
- **Rationale**: `tests/conftest.py` 位于 `testpaths` 根部，pytest 在命令行解析阶段即加载其 `pytest_addoption`；本特性只服务本仓库，无需打包为独立插件。
- **Alternatives considered**: ① 打包独立 pytest 插件（`pytest11` entry-point）——对单仓库测试基建过度设计，且引入包发布义务；② 用 `pytest.ini` 自定义配置项——无法表达「值约束 + 触发交互流程」的语义。

## D2. 交互式异步登录的执行模型（事件循环安全）

- **Decision**: 在 `tests/conftest.py` 的会话级凭据装配逻辑中，用**独立的 `asyncio.run(...)`** 执行登录 / 有效性验证 / 刷新等异步调用，产出普通 `Credential`（纯数据）后交给测试。
- **Rationale**: `get_client()` 按**当前事件循环**维护会话池（`bilibili_api/utils/_session.py:492-499`，`session_pool[selected_client][loop]`），登录流程所在循环关闭后不会污染 pytest-asyncio 为各用例创建的循环——每个循环按需新建自己的客户端实例。宪章「库代码禁用 `asyncio.run()`」只约束 `bilibili_api/`，conftest 属于调用方/测试基建，不受限。
- **Alternatives considered**: ① 把登录做成 `pytest_asyncio` 异步 fixture——session 级异步 fixture 与 `asyncio_default_fixture_loop_scope="function"` 的默认循环策略耦合，跨循环行为反而更难推理；② 在 `bilibili_api/` 里加同步登录包装——直接违反宪章 I（异步优先）。

## D3. 二维码通道的交互细节

- **Decision**: `QrCodeLogin()`（WEB 渠道）→ `generate_qrcode()` → 打印 `get_qrcode_terminal()` 的终端二维码 → 以约 2 秒间隔轮询 `check_state()`；`SCAN`/`CONF` 继续等待，`TIMEOUT` 时重新 `generate_qrcode()` 并提示重新扫码（连续 3 次后中止），`DONE` 后 `get_credential()` 取凭据。
- **Rationale**: `QrCodeLoginEvents` 四态与 spec 的续期+上限策略精确对应（`login_v2.py:366-379`）；`qrcode_terminal` 已是项目依赖，终端 ASCII 二维码无需额外窗口。（`generate_qrcode()` 本身还会顺手在 TEMP 写一张 `qrcode.png`，属于库既有行为，不干预。）
- **Alternatives considered**: ① 用 `get_qrcode_picture()` 弹图片——依赖桌面环境，CI/远程终端不友好；② TV 渠道——cookie 结构不同且非本特性诉求。

## D4. 手机号短信通道的交互细节（含极验）

- **Decision**: `input()` 收集国家码（默认 `+86`）与手机号 → `Geetest().generate_test(GeetestType.LOGIN)` + `start_geetest_server()` → 终端打印 `get_geetest_server_url()` 让用户在浏览器完成滑块验证 → 轮询 `has_done()` → `send_sms()` 得 `captcha_key` → `input()` 收集短信验证码 → `login_with_sms()`；若返回 `LoginCheck`（status 5 风控二次验证），则用 `GeetestType.VERIFY` 走 `LoginCheck.send_sms()` + `complete_check()` 完成收尾，最后关闭极验本地服务。
- **Rationale**: 库已内置本地极验服务（`bilibili_api/utils/geetest.py`，页面在 `bilibili_api/data/geetest/captcha.html`，随 ca73d2d 入库），无需自建验证码前端；`LoginCheck` 分支是 `login_with_sms` 声明的合法返回（`login_v2.py:293-303`）。
- **Alternatives considered**: 密码登录通道（`login_with_password`）——spec 明确只要手机号与二维码两种，且密码经手测试工具有更大的泄露面。

## D5. 凭据有效性验证与刷新路径

- **Decision**: 缓存内容合法 → `Credential.check_valid()`（`isLogin`）判定：`True` 直接使用；`False` 视为过期 → 若缓存含 `ac_time_value` 则调 `Credential.refresh()`（就地更新 sessdata/bili_jct/dedeuserid/ac_time_value，`_credential.py:246-254`）→ 成功则以新凭据**回写缓存文件**并继续；无 `ac_time_value` 或 `refresh()` 抛异常均按「刷新失败」处理（警告 + 删除 + 跳过）。`check_valid()` 自身抛网络/接口异常时按「无法验证」处理（提示 + 跳过，不删文件）。
- **Rationale**: `refresh()` 的刷新材料就是 `ac_time_value`（SMS/QR 登录返回值天然携带，`login_v2.py:345/506`）；缺失即无可刷新，与 spec「刷新所需的配套材料不在缓存中 → 视为刷新失败」一致。`check_refresh()`（返回「是否需要刷新」布尔）在本流程里信息量被 `check_valid()` 覆盖，不额外调用以减少请求次数（412 风控考量）。
- **Alternatives considered**: 先 `check_refresh()` 再 `refresh()`——多一次远程调用且不改变分支结果。

## D6. 缓存文件的位置、命名与编码格式

- **Decision**: 路径 = `tempfile.gettempdir() / "bilibili_api_pytest_login.json"`；内容 = `base64(UTF-8 JSON)`，JSON 键为 `sessdata` / `bili_jct` / `buvid3` / `buvid4` / `dedeuserid` / `ac_time_value`（缺失键容忍，详见 [contracts/cache-file-format.md](contracts/cache-file-format.md)）。
- **Rationale**: `tempfile.gettempdir()` 在 Windows 读 `TEMP`、Unix 读 `TMPDIR`，正是「系统环境变量的 TEMP 文件夹」的可移植实现；固定名称满足 spec「后续运行可寻回 + 后登录覆盖先登录」。
- **Alternatives considered**: ① 含用户名/项目哈希的动态文件名——违反 spec「固定名称」决议；② 明文 JSON——违反用户显式要求的 base64 编码；③ pickle——反序列化不安全（宪法：解析不受信数据须安全方式）。

## D7. 「内容不对」的判定标准

- **Decision**: 满足以下任一即判坏：文件读取失败 / base64 解码失败 / UTF-8 JSON 解析失败 / JSON 顶层不是对象 / 缺少 `sessdata`、`bili_jct`、`dedeuserid` 任一必需字段（字段值为空串等同缺失）。
- **Rationale**: 这三项正是 conftest 现行 `credential` fixture 判定「凭据可用」的必要字段（`conftest.py:85`）；`ac_time_value` 不列入必需（缺失仅意味着不可刷新，按 D5 降级），`buvid3`/`buvid4` 不列入必需（反爬层会自动生成，`get_buvid()`）。
- **Alternatives considered**: 把 `ac_time_value` 也设为必需——会让「能登录但不可刷新」的凭据被误删，与 spec「内容正确→验证→过期→刷新失败才删」的顺序矛盾。

## D8. 凭据来源优先级与既有机制整合

- **Decision**: 解析顺序为：本次 `--login` 新凭据 > TEMP 缓存（经 D5 校验/刷新后的可用凭据）> `BILI_*` 环境变量 > `.bilibili.cookie`（后两者维持 conftest 现行 `_load_credential_values()` 逻辑与顺序不变）。缓存**不可用**时（缺失/已删除/校验失败），完全回退到既有链路，输出与行为同现状。
- **Rationale**: clarify 会话已确认「缓存最高」（2026-08-31）；「无缓存零回归」由回退链路保证（SC-005）。
- **Alternatives considered**: 缓存仅在与 cookie/env 并存时提示冲突——多余交互，无信息增量。

## D9. 用户可见消息的呈现方式

- **Decision**: FileNotFound → 终端一条提示（`pytest` terminal writer）后按回退链路解析，若最终无凭据则 `pytest.skip`；内容不对 → 终端一条错误 + 删除文件 + skip；过期刷新失败 → `warnings.warn(UserWarning)`（pytest 会以 warning 形式呈现，满足「抛出警告」）+ 删除文件 + skip；无法验证 → 提示 + skip（不删文件）。所有消息只描述状态（如「缓存凭据文件内容不合法，已删除」），不含任何凭据字段值。
- **Rationale**: skip reason 会进入 pytest 摘要，天然满足「恰好一条反馈 + 需凭据用例 100% 跳过」的可观测性；`UserWarning` 是「警告而非异常终止」的标准表达。宪法「禁 print() 调试」针对库代码调试输出，测试工装的用户引导消息走 pytest terminal writer 通道。
- **Alternatives considered**: 全部用 `logging`——pytest 默认不展示，用户在终端看不到反馈，违背「输出一条提示」的诉求。

## D10. Windows / 控制台编码风险

- **Decision**: 二维码与中文提示统一经 UTF-8 安全输出路径；实现时注意 Windows cp936 控制台下终端二维码的显示（本项目开发主环境为 Windows + Git Bash）。
- **Rationale**: 本仓库既有经验：cp936 下 GBK 显示正常、UTF-8 反显乱码，勿在显示异常时误判数据损坏。
- **Alternatives considered**: 无（风险登记 + 实现阶段验证）。
