"""
淘宝平台适配器
"""
import time
import hashlib
from decimal import Decimal
from typing import Optional, List
from urllib.parse import urlencode, parse_qs, urlparse

import httpx

from models import ProductInfo, SearchResult, PlatformType, CouponInfo
from config import PlatformConfig, get_settings
from platforms.base import PlatformAdapter
from core.exceptions import APIError, ParseError, ProductNotFoundError, LinkConvertError
from core.logger import logger


class TaobaoAdapter(PlatformAdapter):
    """淘宝/天猫平台适配器"""

    API_GATEWAY = "https://eco.taobao.com/router/rest"

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.settings = get_settings()
        self.app_key = self.settings.TAOBAO_APP_KEY
        self.app_secret = self.settings.TAOBAO_APP_SECRET
        self.adzone_id = self.settings.TAOBAO_ADZONE_ID
        self.site_id = self.settings.TAOBAO_SITE_ID
        self.session = self.settings.TAOBAO_SESSION

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.TAOBAO

    def _generate_sign(self, params: dict) -> str:
        """生成淘宝API签名"""
        # 按参数名排序
        sorted_params = sorted(params.items())
        # 拼接字符串
        sign_str = self.app_secret + ''.join([f"{k}{v}" for k, v in sorted_params]) + self.app_secret
        # MD5加密
        return hashlib.md5(sign_str.encode()).hexdigest().upper()

    async def _call_api(self, method: str, params: dict = None, session: str = None) -> dict:
        """调用淘宝API"""
        if not self.app_key or not self.app_secret:
            raise APIError("淘宝客配置未设置", platform="taobao")

        # 淘宝API要求北京时间（东八区）
        from datetime import datetime, timedelta
        beijing_time = datetime.utcnow() + timedelta(hours=8)
        timestamp = beijing_time.strftime("%Y-%m-%d %H:%M:%S")

        base_params = {
            "app_key": self.app_key,
            "method": method,
            "format": "json",
            "v": "2.0",
            "sign_method": "md5",
            "timestamp": timestamp,
        }

        # SC接口需要session
        if session:
            base_params["session"] = session

        if params:
            base_params.update(params)

        # 生成签名
        base_params["sign"] = self._generate_sign(base_params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.API_GATEWAY, data=base_params)
                response.raise_for_status()
                data = response.json()

                if "error_response" in data:
                    error = data["error_response"]
                    raise APIError(
                        f"{error.get('msg', 'Unknown error')}",
                        platform="taobao",
                        status_code=error.get("code")
                    )

                return data

        except httpx.HTTPError as e:
            logger.error(f"淘宝API请求失败: {e}")
            raise APIError(f"请求失败: {str(e)}", platform="taobao")

    async def parse_link(self, link: str) -> Optional[str]:
        """解析淘宝链接"""
        if not await self.is_valid_link(link):
            return None

        # 尝试直接提取ID
        item_id = self._extract_item_id(link)
        if item_id:
            return item_id

        # 如果是短链接，需要展开
        if "tb.cn" in link:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                    # 使用 GET 请求而不是 HEAD，很多短链接不支持 HEAD
                    response = await client.get(link, headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
                    })
                    expanded_url = str(response.url)
                    logger.info(f"淘宝短链接展开: {link} -> {expanded_url}")
                    return self._extract_item_id(expanded_url)
            except Exception as e:
                logger.warning(f"展开淘宝短链接失败: {e}")
                return None

        return None

    async def get_product_info(self, item_id: str) -> ProductInfo:
        """获取淘宝商品信息"""
        try:
            # 调用淘宝客商品详情API
            result = await self._call_api(
                "taobao.tbk.item.info.get",
                {
                    "fields": "num_iid,title,pict_url,zk_final_price,reserve_price,volume,nick",
                    "num_iids": item_id,
                }
            )

            items = result.get("tbk_item_info_get_response", {}).get("results", {}).get("n_tbk_item", [])

            if not items:
                raise ProductNotFoundError(f"商品不存在: {item_id}")

            item = items[0]

            # 获取优惠券信息
            coupon = await self.get_coupon_info(item_id)

            # 构建商品信息
            product = ProductInfo(
                platform=PlatformType.TAOBAO,
                item_id=str(item["num_iid"]),
                title=item.get("title", ""),
                current_price=Decimal(str(item.get("zk_final_price", 0))),
                original_price=Decimal(str(item.get("reserve_price", 0))) if item.get("reserve_price") else None,
                product_image=item.get("pict_url", ""),
                shop_name=item.get("nick", ""),
                sales_count=int(item.get("volume", 0)) if item.get("volume") else None,
            )

            # 设置优惠券
            if coupon:
                product.coupon = CouponInfo(
                    amount=Decimal(str(coupon.get("amount", 0))),
                    threshold=Decimal(str(coupon.get("start_fee", 0))),
                    title=coupon.get("title", ""),
                    link=coupon.get("url", ""),
                )

            # 获取推广链接
            try:
                product.promotion_link = await self.convert_link(item_id, "")
            except Exception as e:
                logger.warning(f"获取淘宝推广链接失败: {e}")
                # 使用原始链接作为备选
                product.promotion_link = f"https://item.taobao.com/item.htm?id={item_id}"

            return product

        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取淘宝商品信息失败: {e}")
            raise APIError(f"获取商品信息失败: {str(e)}", platform="taobao")

    async def convert_link(self, item_id: str, original_link: str) -> str:
        """转换淘宝链接为推广链接"""
        if not self.adzone_id:
            raise LinkConvertError("淘宝推广位ID未配置")

        try:
            result = await self._call_api(
                "taobao.tbk.tpwd.create",  # 通用接口，不需要 session
                {
                    "text": "超值优惠",  # 口令弹框内容
                    "url": f"https://item.taobao.com/item.htm?id={item_id}",
                    "logo": "",  # 口令弹框logo
                }
            )

            # 获取淘口令
            data = result.get("tbk_tpwd_create_response", {}).get("data", {})
            tpwd = data.get("model", "")

            if tpwd:
                return f"https://m.tb.cn/{tpwd}"

            # 如果淘口令生成失败，返回普通链接
            return f"https://s.click.taobao.com/g?k={item_id}"

        except Exception as e:
            logger.error(f"淘宝转链失败: {e}")
            # 降级处理：返回原始链接
            return f"https://item.taobao.com/item.htm?id={item_id}"

    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        """搜索淘宝商品"""
        try:
            # 如果没有 session，使用通用搜索接口
            if self.session:
                result = await self._call_api(
                    "taobao.tbk.sc.material.optional",
                    {
                        "q": keyword,
                        "adzone_id": self.adzone_id,
                        "site_id": self.site_id,
                        "page_no": page,
                        "page_size": page_size,
                        "sort": "tk_rate_des",  # 按佣金比率降序
                    },
                    session=self.session
                )
            else:
                # 通用物料搜索接口（不需要 session）
                result = await self._call_api(
                    "taobao.tbk.dg.material.optional",
                    {
                        "q": keyword,
                        "adzone_id": self.adzone_id,
                        "page_no": page,
                        "page_size": page_size,
                        "sort": "tk_rate_des",
                    }
                )

            items = result.get("tbk_sc_material_optional_response", {}).get("result_list", {}).get("map_data", [])

            products = []
            for item in items:
                product = ProductInfo(
                    platform=PlatformType.TAOBAO,
                    item_id=str(item.get("item_id", "")),
                    title=item.get("title", ""),
                    current_price=Decimal(str(item.get("zk_final_price", 0))),
                    original_price=Decimal(str(item.get("reserve_price", 0))) if item.get("reserve_price") else None,
                    product_image=item.get("pict_url", ""),
                    shop_name=item.get("nick", ""),
                    sales_count=int(item.get("volume", 0)) if item.get("volume") else None,
                    commission_rate=Decimal(str(item.get("commission_rate", 0))) / 100 if item.get("commission_rate") else None,
                    promotion_link=item.get("coupon_share_url") or item.get("url", ""),
                )

                # 处理优惠券
                if item.get("coupon_amount"):
                    product.coupon = CouponInfo(
                        amount=Decimal(str(item["coupon_amount"])),
                        threshold=Decimal(str(item.get("coupon_start_fee", 0))),
                        title=item.get("coupon_info", ""),
                    )

                products.append(product)

            return SearchResult(
                keyword=keyword,
                products=products,
                total=len(products),
                platform=PlatformType.TAOBAO,
            )

        except Exception as e:
            logger.error(f"淘宝搜索失败: {e}")
            raise APIError(f"搜索失败: {str(e)}", platform="taobao")

    async def get_coupon_info(self, item_id: str) -> Optional[dict]:
        """获取淘宝商品优惠券"""
        try:
            result = await self._call_api(
                "taobao.tbk.coupon.get",
                {
                    "item_id": item_id,
                    "adzone_id": self.adzone_id,
                }
            )

            data = result.get("tbk_coupon_get_response", {}).get("results", {}).get("tbk_coupon", [])

            if data:
                coupon = data[0]
                return {
                    "amount": coupon.get("amount", 0),
                    "start_fee": coupon.get("start_fee", 0),
                    "title": coupon.get("title", ""),
                    "url": coupon.get("url", ""),
                }

            return None

        except Exception as e:
            logger.warning(f"获取淘宝优惠券失败: {e}")
            return None
