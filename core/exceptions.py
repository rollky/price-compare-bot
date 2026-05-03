"""
自定义异常
"""


class PlatformError(Exception):
    """平台相关错误基类"""
    pass


class APIError(PlatformError):
    """API调用错误"""

    def __init__(self, message: str, platform: str = None, status_code: int = None):
        super().__init__(message)
        self.platform = platform
        self.status_code = status_code


class ParseError(PlatformError):
    """链接解析错误"""
    pass


class CacheError(Exception):
    """缓存错误"""
    pass


class RateLimitError(APIError):
    """限流错误"""
    pass


class ProductNotFoundError(PlatformError):
    """商品不存在或已下架"""
    pass


class LinkConvertError(PlatformError):
    """转链失败"""
    pass
