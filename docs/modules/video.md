# Module video.py

bilibili_api.video — 视频相关接口。

``` python
from bilibili_api import video
```

- [class Video()](#class-Video)
  - [def \_\_init\_\_()](#def-\_\_init\_\_)
  - [async def add\_tag()](#async-def-add\_tag)
  - [async def add\_to\_toview()](#async-def-add\_to\_toview)
  - [async def appeal()](#async-def-appeal)
  - [async def delete\_from\_toview()](#async-def-delete\_from\_toview)
  - [async def delete\_tag()](#async-def-delete\_tag)
  - [async def get\_ai\_conclusion()](#async-def-get\_ai\_conclusion)
  - [def get\_aid()](#def-get\_aid)
  - [def get\_bvid()](#def-get\_bvid)
  - [async def get\_chargers()](#async-def-get\_chargers)
  - [async def get\_cid()](#async-def-get\_cid)
  - [async def get\_danmaku\_snapshot()](#async-def-get\_danmaku\_snapshot)
  - [async def get\_danmaku\_view()](#async-def-get\_danmaku\_view)
  - [async def get\_danmaku\_xml()](#async-def-get\_danmaku\_xml)
  - [async def get\_danmakus()](#async-def-get\_danmakus)
  - [async def get\_detail()](#async-def-get\_detail)
  - [async def get\_download\_url()](#async-def-get\_download\_url)
  - [async def get\_history\_danmaku\_index()](#async-def-get\_history\_danmaku\_index)
  - [async def get\_info()](#async-def-get\_info)
  - [async def get\_online()](#async-def-get\_online)
  - [async def get\_pages()](#async-def-get\_pages)
  - [async def get\_pay\_coins()](#async-def-get\_pay\_coins)
  - [async def get\_pbp()](#async-def-get\_pbp)
  - [async def get\_player\_info()](#async-def-get\_player\_info)
  - [async def get\_private\_notes\_list()](#async-def-get\_private\_notes\_list)
  - [async def get\_public\_notes\_list()](#async-def-get\_public\_notes\_list)
  - [async def get\_related()](#async-def-get\_related)
  - [async def get\_relation()](#async-def-get\_relation)
  - [async def get\_special\_dms()](#async-def-get\_special\_dms)
  - [async def get\_subtitle()](#async-def-get\_subtitle)
  - [async def get\_tags()](#async-def-get\_tags)
  - [async def get\_up\_mid()](#async-def-get\_up\_mid)
  - [async def get\_video\_snapshot()](#async-def-get\_video\_snapshot)
  - [async def has\_favoured()](#async-def-has\_favoured)
  - [async def has\_liked()](#async-def-has\_liked)
  - [async def has\_liked\_danmakus()](#async-def-has\_liked\_danmakus)
  - [async def is\_episode()](#async-def-is\_episode)
  - [async def is\_forbid\_note()](#async-def-is\_forbid\_note)
  - [async def like()](#async-def-like)
  - [async def like\_danmaku()](#async-def-like\_danmaku)
  - [async def operate\_danmaku()](#async-def-operate\_danmaku)
  - [async def pay\_coin()](#async-def-pay\_coin)
  - [async def recall\_danmaku()](#async-def-recall\_danmaku)
  - [async def report\_start\_watching()](#async-def-report\_start\_watching)
  - [async def report\_watch\_history()](#async-def-report\_watch\_history)
  - [async def send\_danmaku()](#async-def-send\_danmaku)
  - [def set\_aid()](#def-set\_aid)
  - [def set\_bvid()](#def-set\_bvid)
  - [async def set\_favorite()](#async-def-set\_favorite)
  - [async def share()](#async-def-share)
  - [async def submit\_subtitle()](#async-def-submit\_subtitle)
  - [async def triple()](#async-def-triple)
  - [async def turn\_to\_episode()](#async-def-turn\_to\_episode)
- [async def get\_cid\_info()](#async-def-get\_cid\_info)

---

## class Video()

视频类，各种对视频的操作均在里面。




### def \_\_init\_\_()


| name | type | description |
| - | - | - |
| `bvid` | `str \| None, optional` | BV 号. bvid 和 aid 必须提供其中之一。 |
| `aid` | `int \| None, optional` | AV 号. bvid 和 aid 必须提供其中之一。 |
| `credential` | `Credential \| None, optional` | Credential 类. Defaults to None. |


### async def add_tag()

添加标签。


| name | type | description |
| - | - | - |
| `name` | `str` | 标签名字。 |

**Returns:** `dict`:  调用 API 返回的结果。会返回标签 ID。




### async def add_to_toview()

添加视频至稍后再看列表



**Returns:** `dict`:  调用 API 返回的结果




### async def appeal()

投诉稿件


| name | type | description |
| - | - | - |
| `reason` | `Any` | 投诉类型。传入 VideoAppealReasonType 中的项目即可。 |
| `detail` | `str` | 详情信息。 |

**Returns:** `dict`:  调用 API 返回的结果




### async def delete_from_toview()

从稍后再看列表删除视频



**Returns:** `dict`:  调用 API 返回的结果




### async def delete_tag()

删除标签。


| name | type | description |
| - | - | - |
| `tag_id` | `int` | 标签 ID。 |

**Returns:** `dict`:  调用 API 返回的结果。




### async def get_ai_conclusion()

获取稿件 AI 总结结果。

cid 和 page_index 至少提供其中一个，其中 cid 优先级最高


| name | type | description |
| - | - | - |
| `cid` | `Optional, int` | 分 P 的 cid。 |
| `page_index` | `Optional, int` | 分 P 号，从 0 开始。 |
| `up_mid` | `Optional, int` | up 主的 mid。 |

**Returns:** `dict`:  调用 API 返回的结果。




### def get_aid()

获取 AID。



**Returns:** `int`:  aid。




### def get_bvid()

获取 BVID。



**Returns:** `str`:  BVID。




### async def get_chargers()

获取视频充电用户。



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_cid()

获取稿件 cid


| name | type | description |
| - | - | - |
| `page_index` | `int` | 分 P |

**Returns:** `int`:  cid




### async def get_danmaku_snapshot()

获取弹幕快照



**Returns:** `dict`:  调用 API 返回的结果




### async def get_danmaku_view()

获取弹幕设置、特殊弹幕、弹幕数量、弹幕分段等信息。


| name | type | description |
| - | - | - |
| `page_index` | `int, optional` | 分 P 号，从 0 开始。Defaults to None |
| `cid` | `int, optional` | 分 P 的 ID。Defaults to None |

**Returns:** `dict`:  调用 API 返回的结果。




### async def get_danmaku_xml()

获取所有弹幕的 xml 源文件（非装填）


| name | type | description |
| - | - | - |
| `page_index` | `int, optional` | 分 P 序号. Defaults to 0. |
| `cid` | `int \| None, optional` | cid. Defaults to None. |

**Returns:** `str`:  xml 文件源




### async def get_danmakus()

获取弹幕。


| name | type | description |
| - | - | - |
| `page_index` | `int, optional` | 分 P 号，从 0 开始。Defaults to None |
| `date` | `datetime.Date \| None, optional` | 指定日期后为获取历史弹幕，精确到年月日。Defaults to None. |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |
| `from_seg` | `int, optional` | 从第几段开始(0 开始编号，None 为从第一段开始，一段 6 分钟). Defaults to None. |
| `to_seg` | `int, optional` | 到第几段结束(0 开始编号，None 为到最后一段，包含编号的段，一段 6 分钟). Defaults to None. |

**Returns:** `List[Danmaku]`:  Danmaku 类的列表。


注意：
- 1. 段数可以通过视频时长计算。6分钟为一段。
- 2. `from_seg` 和 `to_seg` 仅对 `date == None` 的时候有效果。
- 3. 例：取前 `12` 分钟的弹幕：`from_seg=0, to_seg=1`



### async def get_detail()

获取视频详细信息



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_download_url()

获取视频下载信息。

返回结果可以传入 `VideoDownloadURLDataDetecter` 进行解析。

page_index 和 cid 至少提供其中一个，其中 cid 优先级最高


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |
| `html5` | `bool, optional` | 是否选择移动端 HTML5 播放流（仅支持 MP4 格式）此时获得的媒体流访问无需鉴权。 |

**Returns:** `dict`:  调用 API 返回的结果。




### async def get_history_danmaku_index()

获取特定月份存在历史弹幕的日期。


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `date` | `datetime.date \| None` | 精确到年月. Defaults to None。 |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |

**Returns:** `None | List[str]`:  调用 API 返回的结果。不存在时为 None。




### async def get_info()

获取视频信息。



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_online()

获取实时在线人数



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_pages()

获取分 P 信息。



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_pay_coins()

获取视频已投币数量。



**Returns:** `int`:  视频已投币数量。




### async def get_pbp()

获取高能进度条


| name | type | description |
| - | - | - |
| `page_index` | `int \| None` | 分 P 号 |
| `cid` | `int \| None` | 分 P 编码 |

**Returns:** `dict`:  调用 API 返回的结果




### async def get_player_info()

获取视频上一次播放的记录，字幕和地区信息。需要分集的 cid, 返回数据中含有json字幕的链接


| name | type | description |
| - | - | - |
| `cid` | `int \| None` | 分 P ID,从视频信息中获取 |
| `epid` | `int \| None` | 番剧分集 ID,从番剧信息中获取 |

**Returns:** `dict`:  调用 API 返回的结果




### async def get_private_notes_list()

获取稿件私有笔记列表。



**Returns:** `list`:  note_Ids。




### async def get_public_notes_list()

获取稿件公开笔记列表。


| name | type | description |
| - | - | - |
| `pn` | `int` | 页码 |
| `ps` | `int` | 每页项数 |

**Returns:** `dict`:  调用 API 返回的结果。




### async def get_related()

获取相关视频信息。



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_relation()

获取用户与视频的关系



**Returns:** `dict`:  调用 API 返回的结果。




### async def get_special_dms()

获取特殊弹幕


| name | type | description |
| - | - | - |
| `page_index` | `int, optional` | 分 P 号. Defaults to 0. |
| `cid` | `int \| None, optional` | 分 P id. Defaults to None. |

**Returns:** `List[SpecialDanmaku]`:  调用接口解析后的结果




### async def get_subtitle()

获取字幕信息


| name | type | description |
| - | - | - |
| `cid` | `int \| None` | 分 P ID,从视频信息中获取 |

**Returns:** `dict`:  调用 API 返回的结果




### async def get_tags()

获取视频标签。


| name | type | description |
| - | - | - |
| `page_index` | `int \| None` | 分 P 序号. Defaults to 0. |
| `cid` | `int \| None` | 分 P 编码. Defaults to None. |

**Returns:** `List[dict]`:  调用 API 返回的结果。




### async def get_up_mid()

获取视频 up 主的 mid。



**Returns:** `int`:  up_mid




### async def get_video_snapshot()

获取视频快照(视频各个时间段的截图拼图)


| name | type | description |
| - | - | - |
| `cid` | `int` | 分 P CID(可选) |
| `json_index` | `bool` | json 数组截取时间表 True 为需要，False 不需要 |
| `pvideo` | `bool` | 是否只获取预览 |

**Returns:** `dict`:  调用 API 返回的结果,数据中 Url 没有 http 头




### async def has_favoured()

是否已收藏。



**Returns:** `bool`:  视频是否已收藏。




### async def has_liked()

视频是否点赞过。



**Returns:** `bool`:  视频是否点赞过。




### async def has_liked_danmakus()

是否已点赞弹幕。


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `ids` | `List[int] \| None` | 要查询的弹幕 ID 列表。 |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |

**Returns:** `dict`:  调用 API 返回的结果。




### async def is_episode()

判断视频是否是番剧



**Returns:** `bool`:  是否是番剧




### async def is_forbid_note()

是否禁止笔记。



**Returns:** `bool`:  是否禁止笔记。




### async def like()

点赞视频。


| name | type | description |
| - | - | - |
| `status` | `bool, optional` | 点赞状态。Defaults to True. |

**Returns:** `dict`:  调用 API 返回的结果。




### async def like_danmaku()

点赞弹幕。


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `dmid` | `int \| None` | 弹幕 ID。 |
| `status` | `bool \| None, optional` | 点赞状态。Defaults to True |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |

**Returns:** `dict`:  调用 API 返回的结果。




### async def operate_danmaku()

操作弹幕


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `dmids` | `List[int] \| None` | 弹幕 ID 列表。 |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |
| `type_` | `DanmakuOperatorType \| None` | 操作类型 |

**Returns:** `dict`:  调用 API 返回的结果。




### async def pay_coin()

投币。


| name | type | description |
| - | - | - |
| `num` | `int, optional` | 硬币数量，为 1 ~ 2 个。Defaults to 1. |
| `like` | `bool, optional` | 是否同时点赞。Defaults to False. |

**Returns:** `dict`:  调用 API 返回的结果。




### async def recall_danmaku()

撤回弹幕


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号 |
| `dmid` | `int` | 弹幕 id |
| `cid` | `int \| None, optional` | 分 P 编码 |

**Returns:** `dict`:  调用 API 返回的结果




### async def report_start_watching()

上报开始观看
该接口亦被用于计算播放量, 播放量更新不是实时的
该接口使用似乎存在 200 播放限制, 请勿滥用!

| name | type | description |
| - | - | - |
| `page_index` | `int \| None` | 分 P 序号 |

**Returns:** `dict`:  调用 API 返回的结果




### async def report_watch_history()

上报观看历史

| name | type | description |
| - | - | - |
| `progress` | `int` | 观看进度 (单位 秒) |
| `page_index` | `int \| None` | 分 P 序号 |
| `cid` | `int \| None` | 分 P ID,从视频信息中获取 |

**Returns:** `dict`:  调用 API 返回的结果




### async def send_danmaku()

发送弹幕。


| name | type | description |
| - | - | - |
| `page_index` | `int \| None, optional` | 分 P 号，从 0 开始。Defaults to None |
| `danmaku` | `Danmaku \| None` | Danmaku 类。 |
| `cid` | `int \| None, optional` | 分 P 的 ID。Defaults to None |

**Returns:** `dict`:  调用 API 返回的结果。




### def set_aid()

设置 aid。


| name | type | description |
| - | - | - |
| `aid` | `int` | AV 号。 |




### def set_bvid()

设置 bvid。


| name | type | description |
| - | - | - |
| `bvid` | `str` | 要设置的 bvid。 |




### async def set_favorite()

设置视频收藏状况。

**如果视频是番剧 `await is_bangumi()`，请转为 `Episode` 类收藏**


| name | type | description |
| - | - | - |
| `add_media_ids` | `List[int], optional` | 要添加到的收藏夹 ID. Defaults to []. |
| `del_media_ids` | `List[int], optional` | 要移出的收藏夹 ID. Defaults to []. |

**Returns:** `dict`:  调用 API 返回结果。




### async def share()

分享视频



**Returns:** `int`:  当前分享数




### async def submit_subtitle()

上传字幕

字幕数据 data 参考：

```json
{
  "font_size": "float: 字体大小，默认 0.4",
  "font_color": "str: 字体颜色，默认 "#FFFFFF"",
  "background_alpha": "float: 背景不透明度，默认 0.5",
  "background_color": "str: 背景颜色，默认 "#9C27B0"",
  "Stroke": "str: 描边，目前作用未知，默认为 "none"",
  "body": [
{
  "from": "int: 字幕开始时间（秒）",
  "to": "int: 字幕结束时间（秒）",
  "location": "int: 字幕位置，默认为 2",
  "content": "str: 字幕内容"
}
  ]
}
```


| name | type | description |
| - | - | - |
| `lan` | `str` | 字幕语言代码，参考 https |
| `data` | `Dict` | 字幕数据 |
| `submit` | `bool` | 是否提交，不提交为草稿 |
| `sign` | `bool` | 是否署名 |
| `page_index` | `int \| None, optional` | 分 P 索引. Defaults to None. |
| `cid` | `int \| None, optional` | 分 P id. Defaults to None. |

**Returns:** `dict`:  API 调用返回结果





### async def triple()

给阿婆主送上一键三连



**Returns:** `dict`:  调用 API 返回的结果




### async def turn_to_episode()

将视频转换为番剧



**Returns:** `Episode`:  番剧对象




---

## async def get_cid_info()

获取 cid 信息 (对应的视频，具体分 P 序号，up 等)



**Returns:** `dict`:  调用 https//hd.biliplus.com 的 API 返回的结果




