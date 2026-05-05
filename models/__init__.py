"""
数据模型
"""
from .product import ProductInfo, PlatformType, PriceHistory, SearchResult, CouponInfo
from .keyword import KeywordItem, KeywordManager, get_keyword_manager

__all__ = [
    "ProductInfo", "PlatformType", "PriceHistory", "SearchResult", "CouponInfo",
    "KeywordItem", "KeywordManager", "get_keyword_manager"
]
