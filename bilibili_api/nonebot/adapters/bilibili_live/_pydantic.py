"""
bilibili_api.nonebot.adapters.bilibili_live._pydantic

pydantic 校验装饰器的类型化别名。

pydantic 的 `model_validator(...)` / `field_validator(...)` 在类型层面返回
`装饰器 | None`，直接作为装饰器使用会被静态检查判定为「不可调用」。这里在
模块级把它收窄为确定的「装饰器」类型，既保留运行时行为，也避免在业务代码里
逐一断言，更不需要新增类型检查豁免。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import field_validator, model_validator

ValidatorDecorator = Callable[[Any], Any]
"""校验器装饰器类型：接收被装饰的方法，返回 pydantic 描述符代理。"""

model_before: ValidatorDecorator = model_validator(mode="before")
"""`mode="before"` 的模型校验器装饰器。"""

model_after: ValidatorDecorator = model_validator(mode="after")
"""`mode="after"` 的模型校验器装饰器。"""


def field_before(*fields: str) -> ValidatorDecorator:
    """
    构造 `mode="before"` 的字段校验器装饰器。

    Args:
        *fields (str): 字段名。

    Returns:
        ValidatorDecorator: 字段校验器装饰器。
    """
    return field_validator(*fields, mode="before")


__all__ = ["ValidatorDecorator", "field_before", "model_after", "model_before"]
