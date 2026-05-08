"""
数据模型
"""
from .product import ProductInfo, PlatformType, PriceHistory, SearchResult, CouponInfo
from .database import Database, get_db
from .keyword import KeywordItem, KeywordManager, get_keyword_manager
from .riddle import RiddleItem, RiddleManager, RiddleGameManager, get_riddle_manager, get_riddle_game_manager

__all__ = [
    "ProductInfo", "PlatformType", "PriceHistory", "SearchResult", "CouponInfo",
    "Database", "get_db",
    "KeywordItem", "KeywordManager", "get_keyword_manager",
    "RiddleItem", "RiddleManager", "RiddleGameManager", "get_riddle_manager", "get_riddle_game_manager"
]
