# Contract: 临时凭据缓存文件格式

**Feature**: 001-pytest-temp-login | **Date**: 2026-08-31 | **Spec**: [spec.md](../spec.md)

## 位置与名称

```text
<tempfile.gettempdir()>/bilibili_api_pytest_login.json
```

- `tempfile.gettempdir()` 解析自系统临时目录环境变量（Windows 读 `TEMP`/`TMP`，Unix 读 `TMPDIR` 等），与规格「系统环境变量的 TEMP 文件夹」对应；
- 文件名**固定**：同机后一次登录覆盖前一次（临时语义），跨次测试运行按此名称寻回。

## 内容格式

文件整体内容为一个 base64 字符串（ASCII，无换行要求），解码后为 UTF-8 编码的 JSON 对象：

```text
file := base64( utf8( json_object ) )

json_object := {
  "sessdata":       str,   // 必需
  "bili_jct":       str,   // 必需
  "dedeuserid":     str,   // 必需
  "ac_time_value":  str,   // 可选——刷新材料；缺失则过期后不可刷新
  "buvid3":         str,   // 可选——缺失时反爬层自动生成
  "buvid4":         str    // 可选——同上
}
```

> 上表字段语义为契约定义；真实文件内容为凭据数据，任何文档/示例中不得出现真实值。

## 合法性判定（「内容正确」的充要条件）

同时满足以下全部条件方为合法，任一失败即「内容不对」（触发删除 + 报错 + 跳过）：

1. 文件存在且可读，内容非空；
2. 内容可被 base64 解码（`base64.b64decode(validate=True)` 语义）；
3. 解码字节为合法 UTF-8，且解析为 JSON 对象（顶层为 object 而非数组/标量）；
4. `sessdata`、`bili_jct`、`dedeuserid` 三键存在且为非空字符串（空串等同缺失）。

## 生命周期规则

| 事件 | 对文件的操作 |
|------|-------------|
| `--login` 登录成功 | 覆盖写入（旧内容无论合法与否一并覆盖） |
| 缓存过期且 `refresh()` 成功 | 以刷新后的凭据覆盖写入 |
| 内容不合法 | 删除 |
| 过期且刷新失败（含无 `ac_time_value`） | 删除 |
| 有效性验证遇网络异常 | 保持原状（不删除） |
| 登录中止 | 保持原状（不写入） |

## 安全边界

- 文件位于本机系统临时目录，永不进入版本库（仓库 `.gitignore` 无需也不应为此添加例外）；
- base64 仅为编码（防误读/防简单泄漏），不构成加密——规格已在 Assumptions 中声明接受；
- 凭据字段值不得出现在日志、终端消息、异常文本中（读取方义务）。
