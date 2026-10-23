"""
bilibili_api.exceptions.VideoUploadException

视频上传过程出错时抛出（如分片上传失败、提交被拒绝）。

历史上承载 VideoUploadException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import VideoUploadException as VideoUploadException

__all__ = ["VideoUploadException"]
