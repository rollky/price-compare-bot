"""
平台适配器抽象基类
所有平台适配器必须继承此类并实现抽象方法
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from decimal import Decimal

from models import ProductInfo, SearchResult, PlatformType
from config import PlatformConfig
from core.exceptions import APIError, ParseError


class PlatformAdapter(ABC):
    """
    平台适配器抽象基类

    所有电商平台（淘宝、京东、拼多多）的适配器都需要继承此类
    并实现以下抽象方法。这保证了上层业务代码可以以统一的方式
    调用不同平台的接口。
    """

    def __init__(self, config: PlatformConfig):
        """
        初始化适配器

        Args:
            config: 平台配置对象
        """
        self.config = config
        self._client = None  # HTTP客户端，延迟初始化

    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """
        返回平台类型标识

        Returns:
            PlatformType枚举值
        """
        pass

    @abstractmethod
    async def parse_link(self, link: str) -> Optional[str]:
        """
        解析商品链接，提取商品ID

        Args:
            link: 原始商品链接（可能包含追踪参数、短链接等）

        Returns:
            商品ID字符串，如果无法解析返回None

        Raises:
            ParseError: 链接格式正确但解析失败
        """
        pass

    @abstractmethod
    async def get_product_info(self, item_id: str) -> ProductInfo:
        """
        获取商品详细信息

        Args:
            item_id: 商品ID

        Returns:
            ProductInfo对象，包含商品完整信息

        Raises:
            ProductNotFoundError: 商品不存在或已下架
            APIError: API调用失败
        """
        pass

    @abstractmethod
    async def convert_link(self, item_id: str, original_link: str) -> str:
        """
        将原始链接转换为推广链接

        Args:
            item_id: 商品ID
            original_link: 原始商品链接

        Returns:
            带推广追踪的链接

        Raises:
            LinkConvertError: 转链失败
        """
        pass

    @abstractmethod
    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        """
        关键词搜索商品

        Args:
            keyword: 搜索关键词
            page: 页码，从1开始
            page_size: 每页数量

        Returns:
            SearchResult对象
        """
        pass

    @abstractmethod
    async def get_coupon_info(self, item_id: str) -> Optional[dict]:
        """
        获取商品可用优惠券信息

        Args:
            item_id: 商品ID

        Returns:
            优惠券信息字典，如果没有可用券返回None
        """
        pass

    async def is_valid_link(self, link: str) -> bool:
        """
        检查链接是否属于该平台

        Args:
            link: 待检查的链接

        Returns:
            True如果是该平台的链接
        """
        if not link:
            return False

        link_lower = link.lower()

        # 检查主域名
        for domain in self.config.domains:
            if domain in link_lower:
                return True

        # 检查短链接域名
        for domain in self.config.short_link_domains:
            if domain in link_lower:
                return True

        return False

    def _extract_item_id(self, link: str) -> Optional[str]:
        """
        使用正则表达式从链接中提取商品ID

        Args:
            link: 商品链接

        Returns:
            提取到的商品ID，如果没有匹配返回None
        """
        for pattern in self.config.item_id_patterns:
            match = pattern.search(link)
            if match:
                return match.group(1)
        return None

    async def close(self):
        """
        关闭适配器，释放资源
        子类可重写此方法进行清理
        """
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
