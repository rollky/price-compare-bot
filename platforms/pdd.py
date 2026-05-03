"""
拼多多平台适配器
"""
import time
import hashlib
from decimal import Decimal
from typing import Optional, List

import httpx

from models import ProductInfo, SearchResult, PlatformType, CouponInfo
from config import PlatformConfig, get_settings
from platforms.base import PlatformAdapter
from core.exceptions import APIError, ParseError, ProductNotFoundError, LinkConvertError
from core.logger import logger


class PDDAdapter(PlatformAdapter):
    """拼多多平台适配器"""

    API_GATEWAY = "https://gw-api.pinduoduo.com/api/router"

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.settings = get_settings()
        self.client_id = self.settings.PDD_CLIENT_ID
        self.client_secret = self.settings.PDD_CLIENT_SECRET
        self.pid = self.settings.PDD_PID

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.PDD

    def _generate_sign(self, params: dict) -> str:
        """生成拼多多API签名"""
        # 拼多多签名规则：
        # 1. 按参数名升序排序
        # 2. 拼接成字符串: client_secret + key1value1 + key2value2 + ... + client_secret
        # 3. MD5加密
        sorted_params = sorted(params.items())
        sign_str = self.client_secret + ''.join([f"{k}{v}" for k, v in sorted_params]) + self.client_secret
        return hashlib.md5(sign_str.encode()).hexdigest().upper()

    async def _call_api(self, method: str, params: dict = None) -> dict:
        """调用拼多多API"""
        if not self.client_id or not self.client_secret:
            raise APIError("拼多多配置未设置", platform="pdd")

        # 拼多多API要求北京时间（东八区）
        from datetime import datetime, timedelta
        beijing_time = datetime.utcnow() + timedelta(hours=8)
        timestamp = str(int(beijing_time.timestamp()))

        base_params = {
            "type": method,
            "client_id": self.client_id,
            "timestamp": timestamp,
            "data_type": "JSON",
            "version": "V1",
        }

        if params:
            base_params.update(params)

        # 生成签名
        base_params["sign"] = self._generate_sign(base_params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.API_GATEWAY, params=base_params)
                response.raise_for_status()
                data = response.json()

                # 拼多多错误处理
                if "error_response" in data:
                    error = data["error_response"]
                    raise APIError(
                        f"{error.get('error_msg', 'Unknown error')}",
                        platform="pdd",
                        status_code=error.get("error_code")
                    )

                return data

        except httpx.HTTPError as e:
            logger.error(f"拼多多API请求失败: {e}")
            raise APIError(f"请求失败: {str(e)}", platform="pdd")

    async def parse_link(self, link: str) -> Optional[str]:
        """解析拼多多链接提取商品ID"""
        if not await self.is_valid_link(link):
            return None

        # 尝试直接提取goods_id
        item_id = self._extract_item_id(link)
        if item_id:
            return item_id

        # 处理短链接
        if "p.pinduoduo.com" in link:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                    # 使用 GET 请求而不是 HEAD，很多短链接不支持 HEAD
                    response = await client.get(link, headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
                    })
                    expanded_url = str(response.url)
                    logger.info(f"拼多多短链接展开: {link} -> {expanded_url}")
                    return self._extract_item_id(expanded_url)
            except Exception as e:
                logger.warning(f"展开拼多多短链接失败: {e}")
                return None

        return None

    async def get_product_info(self, item_id: str) -> ProductInfo:
        """获取拼多多商品信息"""
        try:
            # 调用拼多多商品详情API
            result = await self._call_api(
                "pdd.ddk.goods.detail",
                {
                    "goods_id_list": f"[{item_id}]"
                }
            )

            data = result.get("goods_detail_response", {})
            items = data.get("goods_details", [])

            if not items:
                raise ProductNotFoundError(f"商品不存在: {item_id}")

            item = items[0]

            # 计算券后价
            min_group_price = Decimal(str(item.get("min_group_price", 0))) / 100  # 分转元
            coupon_discount = Decimal(str(item.get("coupon_discount", 0))) / 100

            product = ProductInfo(
                platform=PlatformType.PDD,
                item_id=str(item_id),
                title=item.get("goods_name", ""),
                current_price=min_group_price,
                original_price=Decimal(str(item.get("min_normal_price", 0))) / 100 if item.get("min_normal_price") else None,
                product_image=item.get("goods_image_url", ""),
                shop_name=item.get("mall_name", ""),
                sales_count=int(item.get("sales_tip", 0)) if str(item.get("sales_tip", "")).isdigit() else None,
                commission_rate=Decimal(str(item.get("promotion_rate", 0))) / 1000 if item.get("promotion_rate") else None,
            )

            # 处理优惠券
            if coupon_discount > 0:
                product.coupon = CouponInfo(
                    amount=coupon_discount,
                    threshold=Decimal(str(item.get("coupon_min_order_amount", 0))) / 100,
                    title=f"满{item.get('coupon_min_order_amount', 0)/100}减{coupon_discount}元",
                )

            # 获取推广链接
            try:
                product.promotion_link = await self.convert_link(item_id, "")
            except Exception as e:
                logger.warning(f"获取拼多多推广链接失败: {e}")
                product.promotion_link = f"https://mobile.yangkeduo.com/goods.html?goods_id={item_id}"

            return product

        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取拼多多商品信息失败: {e}")
            raise APIError(f"获取商品信息失败: {str(e)}", platform="pdd")

    async def convert_link(self, item_id: str, original_link: str) -> str:
        """转换拼多多链接为推广链接"""
        if not self.pid:
            raise LinkConvertError("拼多多推广位ID未配置")

        try:
            result = await self._call_api(
                "pdd.ddk.goods.promotion.url.generate",
                {
                    "p_id": self.pid,
                    "goods_id_list": f"[{item_id}]",
                    "generate_short_url": True,
                }
            )

            data = result.get("goods_promotion_url_generate_response", {})
            urls = data.get("goods_promotion_url_list", [])

            if urls:
                # 优先返回短链接
                short_url = urls[0].get("short_url", "")
                if short_url:
                    return short_url
                return urls[0].get("url", "")

            # 降级处理
            return f"https://mobile.yangkeduo.com/goods.html?goods_id={item_id}"

        except Exception as e:
            logger.error(f"拼多多转链失败: {e}")
            return f"https://mobile.yangkeduo.com/goods.html?goods_id={item_id}"

    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        """搜索拼多多商品"""
        try:
            result = await self._call_api(
                "pdd.ddk.goods.search",
                {
                    "keyword": keyword,
                    "page": page,
                    "page_size": page_size,
                    "sort_type": 6,  # 按佣金比例排序
                }
            )

            data = result.get("goods_search_response", {})
            items = data.get("goods_list", [])

            products = []
            for item in items:
                min_group_price = Decimal(str(item.get("min_group_price", 0))) / 100
                coupon_discount = Decimal(str(item.get("coupon_discount", 0))) / 100

                product = ProductInfo(
                    platform=PlatformType.PDD,
                    item_id=str(item.get("goods_id", "")),
                    title=item.get("goods_name", ""),
                    current_price=min_group_price,
                    product_image=item.get("goods_thumbnail_url", ""),
                    shop_name=item.get("mall_name", ""),
                    commission_rate=Decimal(str(item.get("promotion_rate", 0))) / 1000 if item.get("promotion_rate") else None,
                )

                if coupon_discount > 0:
                    product.coupon = CouponInfo(
                        amount=coupon_discount,
                        threshold=Decimal(str(item.get("coupon_min_order_amount", 0))) / 100,
                    )

                products.append(product)

            return SearchResult(
                keyword=keyword,
                products=products,
                total=len(products),
                platform=PlatformType.PDD,
            )

        except Exception as e:
            logger.error(f"拼多多搜索失败: {e}")
            raise APIError(f"搜索失败: {str(e)}", platform="pdd")

    async def get_coupon_info(self, item_id: str) -> Optional[dict]:
        """获取拼多多商品优惠券"""
        # 拼多多的优惠券信息在商品详情中已包含
        # 如果需要单独查询，可以调用相关API
        try:
            return None
        except Exception as e:
            logger.warning(f"获取拼多多优惠券失败: {e}")
            return None
