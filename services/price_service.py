"""
价格查询服务
协调各平台适配器查询商品信息
"""
from typing import Optional, List

from models import ProductInfo, PlatformType, SearchResult
from platforms import ADAPTERS
from config import PLATFORM_CONFIGS, get_settings
from services.cache import CacheService
from core.exceptions import APIError, ProductNotFoundError
from core.logger import logger


class PriceService:
    """
    价格查询服务

    统一的商品信息查询入口，负责：
    1. 缓存优先查询
    2. 调用各平台适配器
    3. 异常处理和降级
    """

    def __init__(self):
        self.cache = CacheService()
        self.adapters = {}
        self._init_adapters()

    def _init_adapters(self):
        """初始化平台适配器"""
        for code, adapter_class in ADAPTERS.items():
            config = PLATFORM_CONFIGS.get(code)
            if config:
                self.adapters[code] = adapter_class(config)

    async def initialize(self):
        """初始化服务（连接缓存）"""
        await self.cache.connect()

    async def shutdown(self):
        """关闭服务"""
        await self.cache.disconnect()

        # 关闭所有适配器
        for adapter in self.adapters.values():
            await adapter.close()

    async def get_product(
        self,
        platform: PlatformType,
        item_id: str,
        use_cache: bool = True,
        force_refresh: bool = False,
        extra: dict = None
    ) -> ProductInfo:
        """
        获取商品信息

        Args:
            platform: 平台类型
            item_id: 商品ID
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新（忽略缓存）
            extra: 额外参数（如拼多多的 goods_sign）

        Returns:
            ProductInfo对象

        Raises:
            ProductNotFoundError: 商品不存在
            APIError: API调用失败
        """
        # 1. 检查缓存
        if use_cache and not force_refresh:
            cached = await self.cache.get_product(platform, item_id)
            if cached:
                logger.info(f"命中缓存: {platform.value} - {item_id}")
                return cached

        # 2. 调用适配器查询
        adapter = self.adapters.get(platform.value)
        if not adapter:
            raise APIError(f"不支持的平台: {platform.value}")

        try:
            # 对于拼多多，传递 extra 参数（包含 goods_sign）
            if platform == PlatformType.PDD and extra and extra.get("goods_sign"):
                product = await adapter.get_product_info(
                    item_id=item_id,
                    goods_sign=extra.get("goods_sign")
                )
            else:
                product = await adapter.get_product_info(item_id)

            # 3. 写入缓存
            if use_cache:
                await self.cache.set_product(product)

            logger.info(f"商品查询成功: {platform.value} - {item_id}")
            return product

        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"商品查询失败: {platform.value} - {item_id} - {e}")
            raise APIError(f"查询失败: {str(e)}", platform=platform.value)

    async def search(
        self,
        keyword: str,
        platform: Optional[PlatformType] = None,
        page: int = 1,
        page_size: int = 10,
        use_cache: bool = True
    ) -> List[SearchResult]:
        """
        关键词搜索

        Args:
            keyword: 搜索关键词
            platform: 指定平台（None则搜索所有平台）
            page: 页码
            page_size: 每页数量
            use_cache: 是否使用缓存

        Returns:
            搜索结果列表（每个平台一个结果）
        """
        results = []

        # 确定要搜索的平台
        platforms = [platform] if platform else [PlatformType.TAOBAO, PlatformType.JD, PlatformType.PDD]

        for p in platforms:
            try:
                # 检查缓存
                if use_cache:
                    cached = await self.cache.get_search_result(keyword, p)
                    if cached:
                        results.append(SearchResult(
                            keyword=keyword,
                            products=cached,
                            total=len(cached),
                            platform=p
                        ))
                        logger.info(f"{p.value}搜索命中缓存: {keyword}")
                        continue

                # 调用适配器搜索
                adapter = self.adapters.get(p.value)
                if not adapter:
                    logger.warning(f"{p.value}适配器未找到")
                    continue

                logger.info(f"开始{p.value}搜索: {keyword}")
                result = await adapter.search(keyword, page, page_size)

                # 写入缓存
                if use_cache:
                    await self.cache.set_search_result(keyword, result.products, p)

                results.append(result)
                logger.info(f"{p.value}搜索成功: {keyword}, 找到{len(result.products)}个商品")

            except Exception as e:
                logger.error(f"{p.value}搜索失败: {e}")
                # 继续下一个平台，不影响其他平台
                continue

        if not results:
            logger.warning(f"所有平台搜索失败: {keyword}")

        return results

    async def convert_link(
        self,
        platform: PlatformType,
        item_id: str,
        original_link: str
    ) -> str:
        """
        转换链接为推广链接

        Args:
            platform: 平台类型
            item_id: 商品ID
            original_link: 原始链接

        Returns:
            推广链接
        """
        # 检查缓存
        cache_key = f"link:{platform.value}:{item_id}"
        # 这里可以添加链接缓存逻辑

        adapter = self.adapters.get(platform.value)
        if not adapter:
            return original_link

        try:
            promotion_link = await adapter.convert_link(item_id, original_link)
            return promotion_link or original_link
        except Exception as e:
            logger.warning(f"转链失败: {platform.value} - {e}")
            return original_link

    async def compare_prices(
        self,
        title: str,
        platforms: Optional[List[PlatformType]] = None
    ) -> List[ProductInfo]:
        """
        比价功能：在多个平台搜索同一商品并比价

        Args:
            title: 商品标题/关键词
            platforms: 要比价的平台（默认全部）

        Returns:
            各平台的商品信息列表（按价格排序）
        """
        platforms = platforms or [PlatformType.TAOBAO, PlatformType.JD, PlatformType.PDD]

        all_products = []

        for p in platforms:
            try:
                results = await self.search(title, platform=p, page_size=3)
                if results and results[0].products:
                    # 取第一个最匹配的结果
                    all_products.append(results[0].products[0])
            except Exception as e:
                logger.warning(f"{p.value}比价查询失败: {e}")
                continue

        # 按券后价排序
        all_products.sort(key=lambda x: x.final_price)

        return all_products
