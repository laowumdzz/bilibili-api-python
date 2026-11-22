# 第三方许可与归属声明（THIRD PARTY NOTICES）

本仓库整体以 **GNU General Public License v3.0 or later（GPL-3.0-or-later）** 分发，
完整文本见 [LICENSE](LICENSE)。

以下第三方代码已融合进本仓库，其原始许可与版权声明如下。

## nonebot-adapter-bilibili-live

- 项目名称：`nonebot-adapter-bilibili-live`
- 基线版本：`0.2.6`
- 基线 commit：`3f2c9bc2e74e02eaeb1a2192335f84eb3391782e`
- 来源仓库：<https://github.com/MingxuanGame/nonebot-adapter-bilibili-live>
- 融合所用 fork：<https://github.com/laowumdzz/nonebot-adapter-bilibili-live>
- 版权行：`Copyright (c) 2025 MingxuanGame`
- 许可：MIT License

融合范围：

- `bilibili_api/nonebot/adapters/bilibili_live/`（适配器实现，事件 / 数据模型 / 帧编解码 / 消息段）
- `bilibili_api/nonebot/adapters/bilibili_live/pb/`（由 `protos/*.proto` 经 betterproto 生成）
- `protos/`（随上游一并提供的 `.proto` 定义）
- `nonebot/adapters/bilibili_live/`（兼容导入入口，仅显式再导出）

融合时对上游代码做了以下改动（均为行为修正或基线适配，不改变许可归属）：

1. 修复上游 0.2.6 的三处缺陷：网页 `DANMU_MSG`（无顶层 `data`）被丢弃、
   醒目留言（含中 / 日文变体）因 `KeyError` 无法产生事件、粉丝勋章字段
   `is_light` / `is_lighted` 校验失败。
2. 网络与凭据层下沉到本库：HTTP / WebSocket 改经 `BiliAPIClient`，账号改经
   凭据存储，删除适配器自带的 WBI / buvid 实现。
3. Python 3.10 基线适配与门禁格式化（含生成代码的字段描述符位置调整）。

## MIT License 全文

```text
MIT License

Copyright (c) 2025 MingxuanGame

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
