"""
京东平台适配器
"""
import time
import hashlib
from decimal import Decimal
from typing import Optional, List
from urllib.parse import urlencode

import httpx

from models import ProductInfo, SearchResult, PlatformType, CouponInfo
from config import PlatformConfig, get_settings
from platforms.base import PlatformAdapter
from core.exceptions import APIError, ParseError, ProductNotFoundError, LinkConvertError
from core.logger import logger


class JDAdapter(PlatformAdapter):
    """京东平台适配器"""

    API_GATEWAY = "https://api.jd.com/routerjson"

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.settings = get_settings()
        self.app_key = self.settings.JD_APP_KEY
        self.app_secret = self.settings.JD_APP_SECRET
        self.union_id = self.settings.JD_UNION_ID
        self.position_id = self.settings.JD_POSITION_ID

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.JD

    def _generate_sign(self, params: dict) -> str:
        """生成京东API签名"""
        # 按参数名排序
        sorted_params = sorted(params.items())
        # 拼接字符串: app_secret + 参数 + app_secret
        param_str = ''.join([f"{k}{v}" for k, v in sorted_params])
        sign_str = f"{self.app_secret}{param_str}{self.app_secret}"
        # MD5加密
        return hashlib.md5(sign_str.encode()).hexdigest().upper()

    async def _call_api(self, method: str, params: dict = None) -> dict:
        """调用京东联盟API"""
        if not self.app_key or not self.app_secret:
            raise APIError("京东联盟配置未设置", platform="jd")

        # 京东API要求北京时间（东八区）
        from datetime import datetime, timedelta
        beijing_time = datetime.utcnow() + timedelta(hours=8)
        timestamp = beijing_time.strftime("%Y-%m-%d %H:%M:%S")

        # 构建系统参数
        base_params = {
            "app_key": self.app_key,
            "method": method,
            "v": "1.0",
            "timestamp": timestamp,
            "format": "json",
            "sign_method": "md5",
        }

        # 添加业务参数
        if params:
            base_params["360buy_param_json"] = params

        # 生成签名
        base_params["sign"] = self._generate_sign(base_params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.API_GATEWAY, data=base_params)
                response.raise_for_status()
                data = response.json()

                # 京东API错误处理
                if "error_response" in data:
                    error = data["error_response"]
                    raise APIError(
                        f"{error.get('zh_desc', 'Unknown error')}",
                        platform="jd",
                        status_code=error.get("code")
                    )

                return data

        except httpx.HTTPError as e:
            logger.error(f"京东API请求失败: {e}")
            raise APIError(f"请求失败: {str(e)}", platform="jd")

    async def parse_link(self, link: str) -> Optional[str]:
        """解析京东链接提取商品ID"""
        if not await self.is_valid_link(link):
            return None

        # 尝试直接提取SKU ID
        item_id = self._extract_item_id(link)
        if item_id:
            return item_id

        # 处理短链接
        if "3.cn" in link or "u.jd.com" in link:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                    # 使用 GET 请求而不是 HEAD，很多短链接不支持 HEAD
                    response = await client.get(link, headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
                    })
                    expanded_url = str(response.url)
                    logger.info(f"京东短链接展开: {link} -> {expanded_url}")
                    return self._extract_item_id(expanded_url)
            except Exception as e:
                logger.warning(f"展开京东短链接失败: {e}")
                return None

        return None

    async def get_product_info(self, item_id: str) -> ProductInfo:
        """获取京东商品信息"""
        try:
            # 调用京东商品查询API
            result = await self._call_api(
                "jd.union.open.goods.promotiongoodsinfo.query",
                {
                    "skuIds": item_id
                }
            )

            data = result.get("jd_union_open_goods_promotiongoodsinfo_query_response", {})
            items = data.get("data", [])

            if not items:
                raise ProductNotFoundError(f"商品不存在: {item_id}")

            item = items[0]

            # 构建商品信息
            product = ProductInfo(
                platform=PlatformType.JD,
                item_id=str(item_id),
                title=item.get("goodsName", ""),
                current_price=Decimal(str(item.get("unitPrice", 0))),
                original_price=Decimal(str(item.get("unitPrice", 0))),  # 京东API可能需要单独获取原价
                product_image=item.get("imgUrl", ""),
                shop_name=item.get("shopName", ""),
                sales_count=None,  # 京东API不返回销量
                commission_rate=Decimal(str(item.get("commissionShare", 0))) / 100 if item.get("commissionShare") else None,
            )

            # 获取推广链接
            try:
                product.promotion_link = await self.convert_link(item_id, "")
            except Exception as e:
                logger.warning(f"获取京东推广链接失败: {e}")
                product.promotion_link = f"https://item.jd.com/{item_id}.html"

            return product

        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取京东商品信息失败: {e}")
            raise APIError(f"获取商品信息失败: {str(e)}", platform="jd")

    async def convert_link(self, item_id: str, original_link: str) -> str:
        """转换京东链接为推广链接"""
        if not self.union_id:
            raise LinkConvertError("京东联盟ID未配置")

        try:
            result = await self._call_api(
                "jd.union.open.promotion.common.get",
                {
                    "promotionCodeReq": {
                        "materialId": f"https://item.jd.com/{item_id}.html",
                        "unionId": self.union_id,
                        "positionId": self.position_id or 0,
                    }
                }
            )

            data = result.get("jd_union_open_promotion_common_get_response", {})
            promotion_data = data.get("data", {})
            click_url = promotion_data.get("clickURL", "")

            if click_url:
                return click_url

            # 降级处理
            return f"https://item.jd.com/{item_id}.html"

        except Exception as e:
            logger.error(f"京东转链失败: {e}")
            return f"https://item.jd.com/{item_id}.html"

    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        """搜索京东商品"""
        try:
            result = await self._call_api(
                "jd.union.open.goods.query",
                {
                    "goodsReqDTO": {
                        "keyword": keyword,
                        "pageIndex": page,
                        "pageSize": page_size,
                        "sortName": "commissionShare",  # 按佣金排序
                        "sort": "desc",
                    }
                }
            )

            data = result.get("jd_union_open_goods_query_response", {})
            items = data.get("data", [])

            products = []
            for item in items:
                product = ProductInfo(
                    platform=PlatformType.JD,
                    item_id=str(item.get("skuId", "")),
                    title=item.get("skuName", ""),
                    current_price=Decimal(str(item.get("lowestPrice", 0))),
                    original_price=Decimal(str(item.get("lowestPrice", 0))),
                    product_image=item.get("imageUrl", ""),
                    shop_name=item.get("shopName", ""),
                    commission_rate=Decimal(str(item.get("commissionShare", 0))) / 100 if item.get("commissionShare") else None,
                    promotion_link=item.get("clickURL", ""),
                )
                products.append(product)

            return SearchResult(
                keyword=keyword,
                products=products,
                total=len(products),
                platform=PlatformType.JD,
            )

        except Exception as e:
            logger.error(f"京东搜索失败: {e}")
            raise APIError(f"搜索失败: {str(e)}", platform="jd")

    async def get_coupon_info(self, item_id: str) -> Optional[dict]:
        """获取京东商品优惠券"""
        # 京东联盟API优惠券信息通常在商品查询中返回
        # 这里可以单独实现优惠券查询逻辑
        try:
            # 京东可能需要调用单独的优惠券API
            # 暂时返回None，实际接入时根据京东API文档实现
            return None
        except Exception as e:
            logger.warning(f"获取京东优惠券失败: {e}")
            return None
