"""
平台适配器模块
"""
from .base import PlatformAdapter
from .taobao import TaobaoAdapter
from .jd import JDAdapter
from .pdd import PDDAdapter

# 平台适配器注册表
ADAPTERS = {
    "taobao": TaobaoAdapter,
    "jd": JDAdapter,
    "pdd": PDDAdapter,
}

__all__ = [
    "PlatformAdapter",
    "TaobaoAdapter",
    "JDAdapter",
    "PDDAdapter",
    "ADAPTERS",
]
