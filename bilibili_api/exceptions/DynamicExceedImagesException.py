"""
bilibili_api.exceptions.DynamicExceedImagesException

动态携带的图片数量超过上限时抛出。

历史上承载 DynamicExceedImagesException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import DynamicExceedImagesException as DynamicExceedImagesException

__all__ = ["DynamicExceedImagesException"]
