"""
配置模块
"""
from .settings import Settings, get_settings
from .platforms import PlatformConfig, PLATFORM_CONFIGS

__all__ = ["Settings", "get_settings", "PlatformConfig", "PLATFORM_CONFIGS"]
