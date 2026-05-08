"""
平台适配器模块（当前仅支持拼多多）
"""
from .base import PlatformAdapter
from .pdd import PDDAdapter

# 平台适配器注册表
ADAPTERS = {
    "pdd": PDDAdapter,
}

__all__ = [
    "PlatformAdapter",
    "PDDAdapter",
    "ADAPTERS",
]
