# Research: 清零 pyrefly 存量类型错误（1064 条）

**Feature**: 005-pyrefly-type-debt | **Date**: 2026-09-25 | **Status**: Complete

数据来源：2026-09-25 以棘轮同口径命令实测（pyrefly 1.2.0，
`pyrefly check ./bilibili_api/ --error <9 码> --output-format min-text --color never`），
全量输出存档于本节附录口径说明。

---

## R1: 1064 条存量的结构性成因（根因聚类）

**Finding**: 逐码逐消息模板聚类后，1064 条不是 1064 个独立问题，而是
少数系统性根因的放大，且存在明确的传导链。

### 根因 A —— `Api.request()/result` 的联合返回类型（最大杠杆）

`bilibili_api/utils/_api.py:432` 的 `Api.result` 属性与 `Api.request()`
均声明为 `int | str | dict | bytes | None`（诚实反映 raw/byte 模式与
各端点差异），但全库约 380 个模块函数声明 `-> dict` 并直接
`return await Api(**api).update_params(**params).result`，产生 bad-return；
该联合类型随返回值流入局部变量后，对变量做下标（`info["list"]`）即产生
bad-index（`Cannot index into int/str/bytes` 共 230/280），做 `.get()/.decode()`
产生部分 missing-attribute，做嵌套 setitem 产生部分 unsupported-operation。

**直接与间接归因估计：600–750 条（占总量约 6 成）**。修好这一层，
下游错误大批消失而非逐条修。

### 根因 B —— `_live_danmaku.py` Protobuf 解码累加器（67 条聚集）

弹幕 protobuf 解码以"条件分支逐 key 写入"方式构建 dict（如
`_live_danmaku.py:38-98`），pyrefly 从首个赋值推断 `dict[str, str]` 后续
写入 bool/dict 失败（`Cannot set item in dict[str,str]` 为主）。
此类累加器的诚实类型就是开放式 JSON 形状（`dict[str, Any]` 级别），
属于"值类型异构是设计意图"的场景，与消音不同。

### 根因 C —— 真 bug 与局部签名错误（散布，约 40–60 条）

抽样核实的确凿实例（均在修复时逐个现场复核）：

| 位置 | 现象 | 初步定性 |
|------|------|----------|
| `channel_series.py:231` | `ChannelSeries(...).get_meta()["total"]` 漏 `await`，协程直接下标 | **真 bug**（运行时 TypeError） |
| `cheese.py:345` | `self.get_meta()["duration"]` 漏 `await` | **真 bug**（同上） |
| `bangumi.py:757/800/830/860/892` | `year: str = -1` 默认值与注解矛盾 | 注解错误，放宽为 `str \| int` 即可（17 条 bad-function-definition 主体） |
| `emoji.py:13` | `credential: Credential = None` | 注解错误 → `Credential \| None = None`（库内既有惯例） |
| `bangumi.py:1174/1199` | `cursor` 声明 int 实际赋 str | 注解或调用错误，现场定 |
| `audio_uploader.py:649-682` | 迭代 `None`（11 条 not-iterable 主体） | 可选参数缺省路径，`or []` 类修法 |
| `session.py:465` | `Session.on` 覆盖父类参数名不一致（bad-override-param-name） | 兼容性敏感：改参数名破坏关键字调用方，见 R6 |
| `video_uploader.py:322/497` | 类体内定义方法名 `__dict__` 覆盖 object 槽位 | 疑似死代码（实例访问 `__dict__` 走槽位不走该方法），实现时全库检索调用点后改名/移除 |
| `dynamic.py:597-604`、`comment.py:383`、`creative_center.py:672` | dict 值类型声明与实际写入不符 | 逐个现场定 |

### 残留码 3 条（R7 详述）

`session.py:465`（bad-override-param-name）与 `video_uploader.py:322/497`
（bad-override-mutable-attribute），全部落入根因 C 表内，无独立工作面。

**Decision**: 按"根因层 → 模块清扫 → 收尾退役"组织修复，而不是按错误码
垂直切割（纯按码切割会与根因结构对撞：修 bad-return 的正确解法同时消掉
大批 bad-index）。

**Rationale**: 根因 A 一个杠杆覆盖约 6 成存量；根因结构决定批次形状。

**Alternatives considered**: ① 纯按错误码逐码清零（spec FR-002 字面主线）——
会在修 bad-return 时被迫先处理其下游 bad-index 的假关联，批次间互相牵制；
② 纯按文件/模块扫——对小而散的码（not-iterable 等集中于个别文件）反而
低效。采用混合：**执行批次按根因/模块切分，验收台账仍按错误码记账**
（棘轮天然按码计数，与 spec FR-002 的"清零退役"验收单位一致）。

---

## R2: 根因 A 的修复设计——中心化类型收窄访问器

**Decision**: 在 `Api` 上新增**类型化结果访问器**（如 `result_dict` /
对应 list、str 等的姊妹访问器按需增加），内部完成一次 isinstance 收窄；
`Api.request()` / `Api.result` 保持现有诚实联合类型与行为不变（公共 API
零变更）。各模块函数的调用点从 `.result` 机械迁移到对应访问器，迁移按
模块分批进行。

**Rationale**:
- 收窄只写一次（中心化），替代 380 处 `cast(dict, ...)`——后者是 spec
  FR-004 明令禁止的大面积消音；
- 迁移是机械改写，可与模块清扫合并为同一批次，一次触碰一个文件；
- 迁移过程天然充当"端点真实返回形状普查"：模块声明 `-> dict` 而数据实为
  list 的端点会在迁移中暴露，按 spec FR-005 作为签名 bug 独立处置（放宽
  返回注解是类型层修正，不改运行时行为）。

**Alternatives considered**:
- ① 380 处 `cast(dict, await ...)`：一票否决（消音、丢失端点形状信息）；
- ② 模块函数返回注解全部放宽为联合类型：破坏下游类型体验，公共签名
  大倒退，否决；
- ③ 访问器内 isinstance 失败抛新异常：类型最诚实，但属于行为变更
  （当前非 dict 数据会静默流过）。**实现时优先 cast + 依据注释**；
  若端点普查显示全部 dict 声明端点运行时恒返回 dict，可升级为显式
  isinstance + 明确异常（届时按行为变更单独评估）。此决策留给实现批次，
  本计划只锁定"中心收窄 + 模块迁移"骨架。

---

## R3: 分批策略与错误码退役顺序

**Decision**: 批次序列（tasks 阶段细化为任务）：

1. **批次 0（校准）**：无代码变更，`type_ratchet.py` 基线 bad-argument-type
   69 → 68（实测值），口径对齐。
2. **批次 1（地基）**：`utils/_api.py` 类型化访问器 +（如需）共享收窄
   工具；不含模块迁移，门禁绿即合入。
3. **批次 2..N（模块清扫）**：按文件迁移调用点 + 顺带修复该文件内的
   根因 B/C 实例。批次切分按文件大小（login_v2 73 / _live_danmaku 67 /
   user 65 / live 64 / bangumi 64 / video 60 / video_uploader 53 / dynamic 41
   为第一梯队）与根因聚簇（audio_uploader 的 not-iterable 群、bangumi 的
   bad-function-definition 群适合整文件一次清）。
4. **批次 F（收尾）**：残留 3 条、KNOWN_RESIDUAL 清理、末位错误码退役、
   豁免表清空、棘轮基线清空、pyproject/脚本注释更新、文档再生成。

错误码退役（基线删除 + 豁免移除，spec FR-003 成对动作）不预设顺序，
随批次自然发生；预期小码（not-iterable 13、bad-function-definition 17、
bad-override 20、missing-attribute 35）先退役，大码（bad-return 387、
bad-index 280、unsupported-operation 184）随模块清扫分批下降、末期退役。

**Rationale**: 每批独立门禁绿 + 棘轮下降（spec FR-002/SC-006）；根因
先行使后续批次变成机械活。

**Alternatives considered**: 一次性大分支全修完再合——违反棘轮渐进原则、
review 不可行，否决。

---

## R4: pyrefly 版本与测量口径锁定

**Finding**: pyproject dev 依赖为 `pyrefly>=0.1`（宽松），uv.lock 实锁
**1.2.0**。默认门禁与棘轮同口径实测均基于 1.2.0。

**Decision**: 本特性期间不升级 pyrefly（uv.lock 不动）；一切计数以棘轮
同口径命令输出为准。若期间必须升级（安全修复等），先重测全量计数、
提交说明记录口径变化，再继续批次。

**Rationale**: spec Edge Case 已列口径漂移风险；v18.0.0 曾经历 pyrefly
3.10 泛型误报（用 cast 归一），版本变动会直接扰动 1064 的分母。

**Alternatives considered**: 把 pyproject 收紧为 `pyrefly==1.2.*`——
有利于口径但属于依赖策略变更，超出本特性范围，不做（记录为可选后续）。

---

## R5: 误报处置原则与 cast 用量约束

**Decision**:
- 每一处 cast / 局部忽略必须附注释说明"为何这是工具误报或唯一收窄点"；
- 中心化访问器内的收窄 cast 是**全局唯一批量豁口**（一处，带依据注释）；
- pyrefly 3.10 泛型类误报沿 v18.0.0 先例（commit 09c2766 的 cast 归一）
  逐处判断，不假设同类全部误报；
- 修复后任一错误码计数若因"cast 掩盖"下降而非"类型变准"下降，视为
  不合格修复，review 阻断。

**Rationale**: spec FR-004 的落地判据；防止棘轮数字好看、类型质量没变。

**Alternatives considered**: 引入 mypy/pyright 双引擎交叉验证——增加门禁
复杂度，超出范围，否决。

---

## R6: 兼容性敏感点清单（宪法 V 守门）

**Finding / Decision**:
- `session.py:465` `Session.on(event_type=...)` 参数名与父类
  `AsyncEvent.on(event_name=...)` 不一致：**直接改名会破坏现有
  `on(event_type="...")` 关键字调用方**。处置：优先与父类签名对齐 +
  兼容垫层（如保留旧参数名吸收进 `**kwargs` 并告警 deprecate），或经
  全库检索确认无关键字调用后改名；两案都不可行才局部忽略 + 依据注释。
  实现批次现场定，默认走"对齐 + 兼容垫层"。
- `video_uploader.py` 的 `__dict__` 方法：改名为常规方法（如 `to_dict`）
  前先全库检索调用点；`obj.__dict__` 属性访问在运行时走类型槽位、不经过
  该方法，调用点大概率不存在。
- 新增 `Api` 访问器为**纯增量**公共 API，无兼容风险。
- 所有注解放宽（`str` → `str | int` 等）不改变运行时行为，不属于
  破坏性变更；模块函数返回注解从错误的 `dict` 修正为 `dict | list`
  属于类型层纠错，逐例在批次说明中记录。

**Rationale**: spec FR-005 零破坏目标；上述两处是已知仅有的兼容雷区。

**Alternatives considered**: 一律局部忽略跳过兼容雷区——把债务换个形态
留下，否决。

---

## R7: 残留码 3 条的收编

**Finding**: bad-override-param-name ×1（session.py:465）与
bad-override-mutable-attribute ×2（video_uploader.py:322/497）均已并入
R6 兼容清单处理；修复后从 `type_ratchet.py` 的 `KNOWN_RESIDUAL` 集合
删除并更新注释（spec FR-008）。

**Decision / Rationale / Alternatives**: 见 R6；无独立方案。

---

## R8: 计数口径备注（防止实现期误判）

- 棘轮命令 min-text 输出**按错误条目**计行，同一行可叠加多条（不同码或
  同码多列），故 1064 ≠ pyrefly 汇总的 "suppressed 627"（后者按位置
  去重）。一切验收以**同口径命令的 ERROR 行数**为准，不混用两个数字。
- 基线脚本自身迭代 `BASELINE` 键集合统计，KNOWN_RESIDUAL 不计数；
  退役某码 = 从 BASELINE 删除 + pyproject 移除（spec FR-003）。
- 批次验收同时看"总计数下降"与"无任何码回升"（spec Edge Case 连锁条款）。

---

## 附:实测分布快照（2026-09-25）

按错误码：bad-return 387 / bad-index 280 / unsupported-operation 184 /
bad-argument-type 68（基线 69）/ bad-assignment 57 / missing-attribute 35 /
bad-override 20 / bad-function-definition 17 / not-iterable 13 /
bad-override-mutable-attribute 2 / bad-override-param-name 1，合计 1064。

按文件 Top10：login_v2.py 73 / _live_danmaku.py 67 / user.py 65 /
live.py 64 / bangumi.py 64 / video.py 60 / video_uploader.py 53 /
dynamic.py 41 / cheese.py 38 / watchroom.py 33（共 60 文件）。

消息模板头部：bad-return 380/387 为"联合类型不可赋给声明返回类型"单一
模板；bad-index 280 中 230 为对联合类型下标、43 为对 `object` 下标；
unsupported-operation 90 下标 + 85 setitem + 9 比较操作。
