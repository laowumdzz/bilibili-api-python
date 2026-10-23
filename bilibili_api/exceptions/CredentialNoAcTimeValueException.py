"""
bilibili_api.exceptions.CredentialNoAcTimeValueException

凭据缺少有效的 ac_time_value 时抛出（刷新 cookies 需要该字段）。

历史上承载 CredentialNoAcTimeValueException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoAcTimeValueException as CredentialNoAcTimeValueException

__all__ = ["CredentialNoAcTimeValueException"]
