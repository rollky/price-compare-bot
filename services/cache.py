"""
缓存服务
基于Redis的缓存封装
"""
import json
from typing import Optional, Any
from datetime import datetime

import redis.asyncio as redis
from redis.asyncio import Redis

from models import ProductInfo, PlatformType
from config import get_settings
from core.exceptions import CacheError
from core.logger import logger


class CacheService:
    """
    缓存服务

    提供统一的缓存读写接口，支持商品信息、搜索结果等数据的缓存
    """

    def __init__(self):
        self.settings = get_settings()
        self._redis: Optional[Redis] = None

    async def connect(self):
        """连接Redis"""
        if not self._redis:
            try:
                self._redis = await redis.from_url(
                    self.settings.REDIS_URL,
                    password=self.settings.REDIS_PASSWORD,
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("Redis连接成功")
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                raise CacheError(f"Redis连接失败: {e}")

    async def disconnect(self):
        """断开Redis连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get_product(self, platform: PlatformType, item_id: str) -> Optional[ProductInfo]:
        """
        获取商品缓存

        Args:
            platform: 平台类型
            item_id: 商品ID

        Returns:
            ProductInfo对象，如果缓存不存在返回None
        """
        if not self._redis:
            return None

        try:
            key = f"product:{platform.value}:{item_id}"
            data = await self._redis.get(key)

            if data:
                product_dict = json.loads(data)
                # 重建ProductInfo对象
                return self._dict_to_product(product_dict)

            return None

        except Exception as e:
            logger.warning(f"读取商品缓存失败: {e}")
            return None

    async def set_product(self, product: ProductInfo, ttl: int = None):
        """
        设置商品缓存

        Args:
            product: 商品信息
            ttl: 过期时间（秒），默认使用配置值
        """
        if not self._redis:
            return

        try:
            key = f"product:{product.platform.value}:{product.item_id}"
            data = json.dumps(product.to_dict())
            ttl = ttl or self.settings.CACHE_TTL_PRODUCT

            await self._redis.setex(key, ttl, data)
            logger.debug(f"商品缓存已设置: {key}")

        except Exception as e:
            logger.warning(f"设置商品缓存失败: {e}")

    async def delete_product(self, platform: PlatformType, item_id: str):
        """删除商品缓存"""
        if not self._redis:
            return

        try:
            key = f"product:{platform.value}:{item_id}"
            await self._redis.delete(key)

        except Exception as e:
            logger.warning(f"删除商品缓存失败: {e}")

    async def get_search_result(self, keyword: str, platform: Optional[PlatformType] = None) -> Optional[list]:
        """
        获取搜索结果缓存

        Args:
            keyword: 搜索关键词
            platform: 平台类型（可选）

        Returns:
            商品列表，如果缓存不存在返回None
        """
        if not self._redis:
            return None

        try:
            platform_str = platform.value if platform else "all"
            key = f"search:{platform_str}:{self._hash_keyword(keyword)}"
            data = await self._redis.get(key)

            if data:
                products_dict = json.loads(data)
                return [self._dict_to_product(p) for p in products_dict]

            return None

        except Exception as e:
            logger.warning(f"读取搜索缓存失败: {e}")
            return None

    async def set_search_result(self, keyword: str, products: list, platform: Optional[PlatformType] = None, ttl: int = None):
        """
        设置搜索结果缓存

        Args:
            keyword: 搜索关键词
            products: 商品列表
            platform: 平台类型
            ttl: 过期时间（秒）
        """
        if not self._redis:
            return

        try:
            platform_str = platform.value if platform else "all"
            key = f"search:{platform_str}:{self._hash_keyword(keyword)}"
            data = json.dumps([p.to_dict() for p in products])
            ttl = ttl or self.settings.CACHE_TTL_SEARCH

            await self._redis.setex(key, ttl, data)

        except Exception as e:
            logger.warning(f"设置搜索缓存失败: {e}")

    async def is_rate_limited(self, openid: str) -> bool:
        """
        检查是否触发限流

        Args:
            openid: 用户OpenID

        Returns:
            True如果超过限流阈值
        """
        if not self._redis:
            return False

        try:
            key = f"rate_limit:{openid}"
            current = await self._redis.incr(key)

            if current == 1:
                # 第一次请求，设置过期时间
                await self._redis.expire(key, 60)

            return current > self.settings.RATE_LIMIT_PER_MINUTE

        except Exception as e:
            logger.warning(f"限流检查失败: {e}")
            return False

    def _hash_keyword(self, keyword: str) -> str:
        """对关键词进行哈希（简化存储）"""
        import hashlib
        return hashlib.md5(keyword.lower().strip().encode()).hexdigest()[:16]

    def _dict_to_product(self, data: dict) -> ProductInfo:
        """将字典转换为ProductInfo对象"""
        from decimal import Decimal

        # 处理优惠券
        coupon = None
        if data.get("coupon"):
            coupon = CouponInfo(
                amount=Decimal(data["coupon"]["amount"]),
                threshold=Decimal(data["coupon"]["threshold"]),
                title=data["coupon"]["title"],
                link=data["coupon"].get("link", ""),
            )

        return ProductInfo(
            platform=PlatformType(data["platform"]),
            item_id=data["item_id"],
            title=data["title"],
            current_price=Decimal(data["current_price"]),
            original_price=Decimal(data["original_price"]) if data.get("original_price") else None,
            coupon=coupon,
            commission_rate=Decimal(data["commission_rate"]) if data.get("commission_rate") else None,
            promotion_link=data.get("promotion_link", ""),
            product_image=data.get("product_image", ""),
            shop_name=data.get("shop_name", ""),
            sales_count=data.get("sales_count"),
            rating=data.get("rating"),
            rating_count=data.get("rating_count"),
        )

    async def clear_cache(self):
        """清空所有缓存（谨慎使用）"""
        if not self._redis:
            return

        try:
            await self._redis.flushdb()
            logger.info("缓存已清空")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
