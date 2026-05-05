"""
API模块
"""
from .wechat import wechat_router
from .admin import admin_router

__all__ = ["wechat_router", "admin_router"]
