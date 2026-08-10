# bilibili_api 互动视频受限表达式求值离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

import pytest

from bilibili_api.exceptions import ApiException
from bilibili_api.interactive_video import (
    InteractiveJumpingCommand,
    InteractiveJumpingCondition,
    InteractiveVariable,
)
from bilibili_api.utils.utils import restricted_eval

# 应被安全拒绝的注入表达式（均不得执行任何副作用）
MALICIOUS_EXPRESSIONS = [
    "__import__('os').system('calc')",
    "().__class__.__bases__[0].__subclasses__()",
    "exec('import os')",
    "open('secret.txt')",
    "os",
    "True.__class__",
    "[1, 2][0]",
    "'abc'",
    "9 ** 9 ** 9",  # 超大指数 DoS：指数非常量，应拒绝
    "2 ** 100",  # 指数超过 64，应拒绝
]


def test_restricted_eval_arithmetic():
    """restricted_eval 应支持基础算术与一元运算。"""
    assert restricted_eval("1 + 2 * 3") == 7
    assert restricted_eval("10 - 4 / 2") == 8.0
    assert restricted_eval("7 // 2") == 3
    assert restricted_eval("7 % 3") == 1
    assert restricted_eval("-5 + 3") == -2
    assert restricted_eval("2 ** 10") == 1024


def test_restricted_eval_boolean_and_compare():
    """restricted_eval 应支持布尔与比较运算（保持短路语义）。"""
    assert restricted_eval("True and False") is False
    assert restricted_eval("True or False") is True
    assert restricted_eval("not False") is True
    assert restricted_eval("1 < 2 == 2") is True  # 链式比较
    assert restricted_eval("0 or 5") == 5  # and/or 返回决定结果的操作数
    assert restricted_eval("1 and 0") == 0


@pytest.mark.parametrize("malicious", MALICIOUS_EXPRESSIONS)
def test_restricted_eval_rejects_injection(malicious):
    """注入表达式应全部抛出 ApiException 而非被执行。"""
    with pytest.raises(ApiException):
        restricted_eval(malicious)


def test_restricted_eval_rejects_invalid_syntax():
    """语法非法的表达式应抛出 ApiException（原 eval 则抛出 SyntaxError）。"""
    with pytest.raises(ApiException):
        restricted_eval("1 +")


def test_condition_basic():
    """条件公式在变量替换后应按原语义求值。"""
    var = InteractiveVariable(name="分数", var_id="$score", var_value=60)
    assert InteractiveJumpingCondition(var=[var], condition="").get_result() is True
    assert InteractiveJumpingCondition(var=[var], condition="$score >= 60").get_result() is True
    assert InteractiveJumpingCondition(var=[var], condition="$score > 100").get_result() is False


def test_condition_js_operators():
    """&& / || / === / true / false 等 JS 语法转换后语义应保持不变。"""
    var = InteractiveVariable(name="分数", var_id="$score", var_value=30)
    assert InteractiveJumpingCondition(var=[var], condition="$score > 10 && $score < 60").get_result() is True
    assert InteractiveJumpingCondition(var=[var], condition="$score > 60 || $score === 30").get_result() is True
    assert InteractiveJumpingCondition(var=[var], condition="$score === true").get_result() is False
    flag = InteractiveVariable(name="标志", var_id="$flag", var_value=1)
    assert InteractiveJumpingCondition(var=[flag], condition="$flag === true").get_result() is True
    assert InteractiveJumpingCondition(var=[flag], condition="!( $flag === false )").get_result() is True


def test_condition_arithmetic():
    """条件公式中的算术运算应保持可用。"""
    var = InteractiveVariable(name="分数", var_id="$score", var_value=40)
    assert InteractiveJumpingCondition(var=[var], condition="$score + 20 >= 60").get_result() is True


@pytest.mark.parametrize("malicious", MALICIOUS_EXPRESSIONS)
def test_condition_rejects_injection(malicious):
    """远端下发的恶意条件公式应被安全拒绝，而不是被 eval 执行。"""
    condition = InteractiveJumpingCondition(var=[], condition=malicious)
    with pytest.raises(ApiException):
        condition.get_result()


def test_command_arithmetic():
    """跳转命令应能完成变量算术赋值（主库按变量名匹配；分号后不能有空格，沿用既有解析行为）。"""
    vars_ = [
        InteractiveVariable(name="$a", var_id="$a", var_value=1),
        InteractiveVariable(name="$b", var_id="$b", var_value=2),
    ]
    result = InteractiveJumpingCommand(var=vars_, command="$a = $b + 3;$b = $a * 2").run_command()
    values = {var.get_name(): var.get_value() for var in result}
    assert values["$a"] == 5
    assert values["$b"] == 10


def test_command_empty():
    """空命令应原样返回变量列表。"""
    vars_ = [InteractiveVariable(name="$a", var_id="$a", var_value=1)]
    assert InteractiveJumpingCommand(var=vars_, command="").run_command() is vars_


@pytest.mark.parametrize("malicious", ["$a = __import__('os').system('calc')", "$a = open('secret.txt').read()"])
def test_command_rejects_injection(malicious):
    """远端下发的恶意赋值命令应被安全拒绝。"""
    vars_ = [InteractiveVariable(name="$a", var_id="$a", var_value=1)]
    command = InteractiveJumpingCommand(var=vars_, command=malicious)
    with pytest.raises(ApiException):
        command.run_command()


def test_player_condition_and_command():
    """ivitools 播放器内的同名类应同样拒绝注入表达式（需 PyQt6 环境）。"""
    pytest.importorskip("PyQt6")
    from bilibili_api.tools.ivitools import player

    var = player.InteractiveVariable(name="分数", var_id="$score", var_value=30)
    assert player.InteractiveJumpingCondition(var=[var], condition="$score > 10 && $score < 60").get_result() is True
    with pytest.raises(ApiException):
        player.InteractiveJumpingCondition(var=[], condition="__import__('os').system('calc')").get_result()

    vars_ = [player.InteractiveVariable(name="$a", var_id="$a", var_value=1)]
    result = player.InteractiveJumpingCommand(var=vars_, command="$a = 2 + 3").run_command()
    assert result[0].get_value() == 5
    with pytest.raises(ApiException):
        player.InteractiveJumpingCommand(var=vars_, command="$a = __import__('os')").run_command()
