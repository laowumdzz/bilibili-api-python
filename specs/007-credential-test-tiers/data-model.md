# Data Model: 集成测试按重要程度分级重构（特性 007）

**Date**: 2026-09-26
**依据**: spec.md FR-001 ~ FR-014 + research.md R1 ~ R12

本特性无持久化存储与运行时数据模型；数据模型为**测试套件的分层治理实体**（概念模型 + 权威映射表）。实现载体为 pytest marker、conftest.py 钩子与测试文件本身。

## 实体

### 1. 重要级（Tier）

| 层级 | 语义 | 准入判据（全部满足） | 请求预算 | 清理要求 |
|------|------|----------------------|----------|----------|
| cred0 | 核心冒烟 | 只读；接口稳定（无上游已死容错码）；登录态 + 反爬链路 + 核心读的 minimal 集合 | 整层 ≤ 30 | 无写，无需清理 |
| cred1 | 核心读回归 | 只读；核心模块主读路径；允许保留既有容错码（-404 / -352 / -403 等） | cred0+cred1 合计 ≤ 400 | 无写，无需清理 |
| cred2 | 自清理写生命周期 | 仅限两类操作：①可逆写（存在配对恢复 API 且恢复有断言）；②"自身状态类"白名单操作 | 不设独立预算（默认运行含 cred0+1） | 六态零残留（关注 / 收藏 / 点赞 / 评论 / 弹幕 / 稍后再看） |
| cred3 | 高危显式门控 | 资源消耗类 / 无清理可能的公开发布类 / 破坏性类 / 账号身份特定类 | 无（默认永不执行） | 无（不默认执行，无验收义务） |

**关系**: Tier 1 — N CredentialTest（每个需凭据用例恰好一层）；cred0 额外可标注匿名反爬用例（不强制）。

### 2. 账号安全策略（Account Safety Policy）——操作类别判定表

新增或调整用例时按下表对号入座（权威判据，写入 AGENTS.md 测试节）：

| 类别 | 定义 | 归层 | 现有用例示例 |
|------|------|------|--------------|
| 可逆写 | 存在配对恢复 API，恢复结果可断言 | cred2（配对 + 断言） | like/unlike、fav/unfav、follow/unfollow、评论 send/delete（自有内容）、toview add/remove、收藏夹 CRUD、订阅/取消订阅 |
| 自身状态类 | 不可逆但仅自身可见，不属于六态清单，无对外发布形态 | cred2（成文白名单） | 直播签到、观看上报、互动视频评分 |
| 资源消耗类 | 消耗账号货币 / 付费资源 | cred3 | 投币、三连、金 / 银瓜子送礼、人气票 |
| 公开发布类 | 对他人可见的内容发布 | cred2 仅当：目标为自有内容 **且** 有删除配对；否则 cred3 | 评论（自有视频 + delete → cred2）；弹幕（无 delete → cred3）、私信、投票创建（无 delete → cred3）、直播预约 |
| 破坏性 / 身份特定类 | 不可逆清空账号数据，或需特定账号身份 | cred3 | 清空稍后再看、删除观看记录、创作中心全量、房管封禁 |

**校验规则**: 写目标不可硬编码他人 mid/aid——cred2 公开发布类用例 MUST 运行时动态解析自有内容（`get_self_info` → `User(mid).get_videos()`），解析不到则条件跳过。

**白名单治理（封闭枚举 + 证据义务 + 从严回退）**: "自身状态类"白名单为封闭枚举——新增成员须在权威映射表条目中逐条给出三条件依据（仅自身可见的证据、六态清单对照、无对外发布形态的核查），由 PR 评审者核验；任一条件事后失效时自动降层至 cred3 并同步更新映射表。五类判定表的兜底规则：无法对号入座或未完成举证的操作一律从严归 cred3 待裁。

### 3. 凭据用例（Credential Test）

属性: `tier`（cred0–cred3）、`读/写`、`配对恢复动作`（cred2 可逆写必填）、`估计请求数`（预算表用）、`容错码集合`（上游已死接口，禁止进 cred0）。

### 4. 层级选择器（Tier Selector）——运行入口契约

见 [contracts/test-tier-selection.md](contracts/test-tier-selection.md)。

## 权威分层映射表（38 文件全量）

> 混合文件以用例组标注；未注明的读用例归属该文件主层。`*` = 需要在实现中重构（合并 / 改道 / 采样 / 节流 / 拆分）。

### cred0 — 核心冒烟（12 用例，约 20 请求）

| 文件 | 用例 | 估计请求 |
|------|------|----------|
| test_readonly_smoke.py | 全部 6 个（保留 readonly 模块标记，附加 cred0） | 8 |
| test_video.py | get_info、get_pages、get_tags | 3 |
| test_user.py | get_user_info、get_relation_info | 2 |
| test_search.py | 基础搜索（test_a） | 1 |

### cred1 — 核心读回归（约 150 用例，约 300 请求，cred0+cred1 合计 ≤400）

| 文件 | 归层内容 | 备注 |
|------|----------|------|
| test_video.py | 其余全部读用例（弹幕 view/list/history/xml/snapshot/index、pbp、字幕、related、chargers、has_liked、get_pay_coins、has_favoured、relation、online、snapshot、get_cid_info 等） | |
| test_user.py | 其余全部读用例（约 39 个：videos / media_list / dynamics / followers / followings / history / coins / toview / medal / album 等） | |
| test_dynamic.py | 全部读用例（schedules、get_info、get_reposts、page UPs / info、reaction、lottery 等） | |
| test_live.py | 全部读用例（room info / play info v1+v2 / danmu / gift config / rank 系列 / self info / bag / emoticons / gaonengbang 等） | |
| test_comment.py | get_comments（匿名读） | |
| test_session.py | 9 个读接口 | send_msg → cred3 |
| test_favorite_list.py | 全部读接口（list / content / topic / article / course / note / collected） | 生命周期 → cred2 |
| test_search.py | 其余 8 个 | |
| test_note.py | 全部 6 个（含私有笔记 79502 容错） | |
| test_article.py / test_audio.py / test_topic.py / test_video_tag.py / test_manga.py | 各自读用例 | 写用例另归 |
| test_interactive_video.py | get_graph_version、get_edge_info、图遍历*（节点间 0.5s 节流） | mark_score → cred2 |
| test_rank.py | 除 subscribe_music_rank 外全部；test_a 采样 5 分区*、test_j 采样 3 榜*、phase 链合并* | subscribe_music_rank → cred3 |
| test_hot.py / test_bangumi.py / test_article_category.py / test_video_zone.py / test_live_area.py / test_black_room.py / test_cheese.py / test_client.py / test_emoji.py / test_festival.py / test_game.py / test_video_uploader.py | 全部（匿名读，integration 标记不变，无需 cred 标注） | |
| test_homepage.py / test_app.py / test_show.py | 全部（含凭据读） | homepage test_d 重复调用 get_popularize 顺手去重* |
| test_ass.py | 全部（本地文件输出改 tmp_path*） | |
| test_root_functions.py | 2 个（parse_link 采样 20 形态 + 0.5s 节流*） | |

### cred2 — 自清理写生命周期（约 18 用例）

| 文件 | 生命周期用例（合并后） | 类别 |
|------|------------------------|------|
| test_video.py | like on/off；set_favorite add/remove；toview add/remove；report_watch_history*；report_start_watching* | 可逆写 / 自身状态类 |
| test_comment.py | 评论完整生命周期*（send→reply→like→hate→delete，目标动态解析为自有视频） | 公开发布类（自有 + 可删） |
| test_favorite_list.py | 收藏夹完整生命周期*（create→set→modify→copy→move→clean→delete） | 可逆写 |
| test_user.py | modify_relation subscribe/unsubscribe（既有 test_t 合并闭环） | 可逆写 |
| test_article.py | set_like on/off；set_favorite on/off*（补取消收藏调用） | 可逆写 |
| test_topic.py | like on/off；fav on/off | 可逆写 |
| test_video_tag.py | subscribe/unsubscribe | 可逆写 |
| test_manga.py | follow on/off | 可逆写 |
| test_dynamic.py | set_like on/off*（补取消点赞） | 可逆写 |
| test_watchroom.py | 观影房间完整生命周期*（create→join→share→progress→close→msgs） | 可逆写 |
| test_live.py | 签名 dahanghai + receive_reward（自身状态类，成文） | 自身状态类 |
| test_interactive_video.py | mark_score（自身状态类，成文） | 自身状态类 |

### cred3 — 高危显式门控（默认收集即排除）

| 文件 | 用例 | 类别 |
|------|------|------|
| test_video.py | send_danmaku、pay_coin、triple | 公开发布类（无删除）/ 资源消耗类 |
| test_live.py | send_danmaku ×2、金 / 银 / 背包礼物、人气票、ban/unban（含 black_list 链合并*）、create_live_reserve | 资源消耗 / 身份特定 / 公开发布类 |
| test_session.py | send_msg | 公开发布类 |
| test_creative_center.py | 整文件（19 用例） | 身份特定类 |
| test_rank.py | subscribe_music_rank（无取消订阅，残留） | 公开发布类（无删除） |
| test_user.py | clear_toview_list、delete_viewed_videos_from_toview | 破坏性类 |
| test_vote.py | 投票创建与更新*（create→update 合并；无删除 API） | 公开发布类（无删除） |

### 特殊处置（不入四层）

| 文件 | 处置 |
|------|------|
| test_initial_state.py | 更名 test_offline_initial_state.py，摘除 integration 标记（纯本地解析，宪法 IV 修正） |

## 状态转移

CredentialTest 的 tier 生命周期: `未标注` --(实现期映射)--> `已标注` --(安全策略类别变更 / API 能力变化，如新增 delete_danmaku)--> `重判归层`。重判规则: 按账号安全策略表对号入座，层间迁移须同步更新本表与 AGENTS.md。
