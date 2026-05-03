"""
拼多多平台适配器
"""
import time
import hashlib
from decimal import Decimal
from typing import Optional, List

import httpx

from models import ProductInfo, SearchResult, PlatformType, CouponInfo
from config import PlatformConfig, get_settings, PLATFORM_CONFIGS
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

        # 调试日志
        logger.debug(f"拼多多签名参数: {dict(sorted_params)}")
        logger.debug(f"拼多多签名字符串: {sign_str[:50]}...")
        logger.debug(f"拼多多签名结果: {hashlib.md5(sign_str.encode()).hexdigest().upper()}")

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

        # 打印完整请求参数（调试用）
        import json
        logger.info(f"拼多多API请求参数: {json.dumps(base_params, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.API_GATEWAY, params=base_params)
                response.raise_for_status()
                data = response.json()

                # 拼多多错误处理
                if "error_response" in data:
                    error = data["error_response"]
                    error_msg = error.get('error_msg', 'Unknown error')
                    error_code = error.get("error_code")
                    sub_msg = error.get('sub_msg', '')
                    sub_code = error.get('sub_code', '')

                    # 详细日志，包含子错误
                    logger.error(f"拼多多API错误: code={error_code}, msg={error_msg}, sub_code={sub_code}, sub_msg={sub_msg}")
                    logger.error(f"完整错误响应: {data}")

                    raise APIError(
                        f"{error_msg} (sub_code: {sub_code}, sub_msg: {sub_msg})",
                        platform="pdd",
                        status_code=error_code
                    )

                return data

        except httpx.HTTPError as e:
            logger.error(f"拼多多API请求失败: {e}")
            raise APIError(f"请求失败: {str(e)}", platform="pdd")

    def _extract_goods_sign(self, link: str) -> Optional[str]:
        """从链接中提取goods_sign"""
        import re
        pattern = r'goods_sign=([^&]+)'
        match = re.search(pattern, link)
        if match:
            return match.group(1)
        return None

    async def parse_link(self, link: str) -> Optional[dict]:
        """
        解析拼多多链接
        返回包含 goods_id 和 goods_sign 的字典
        """
        if not await self.is_valid_link(link):
            return None

        result = {
            "goods_id": None,
            "goods_sign": None
        }

        # 尝试直接提取goods_id
        goods_id = self._extract_item_id(link)
        if goods_id:
            result["goods_id"] = goods_id

        # 尝试提取goods_sign
        goods_sign = self._extract_goods_sign(link)
        if goods_sign:
            result["goods_sign"] = goods_sign
            return result

        # 处理短链接
        if "p.pinduoduo.com" in link:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                    response = await client.get(link, headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
                    })
                    expanded_url = str(response.url)
                    logger.info(f"拼多多短链接展开: {link} -> {expanded_url}")

                    # 从展开后的链接提取
                    result["goods_id"] = self._extract_item_id(expanded_url)
                    result["goods_sign"] = self._extract_goods_sign(expanded_url)

                    if result["goods_sign"] or result["goods_id"]:
                        return result
            except Exception as e:
                logger.warning(f"展开拼多多短链接失败: {e}")
                return None

        if result["goods_id"] or result["goods_sign"]:
            return result
        return None

    async def search_by_goods_id(self, goods_id: str) -> Optional[dict]:
        """通过goods_id搜索商品，获取goods_sign"""
        try:
            result = await self._call_api(
                "pdd.ddk.goods.search",
                {
                    "keyword": goods_id,
                    "page": 1,
                    "page_size": 10,
                }
            )

            data = result.get("goods_search_response", {})
            items = data.get("goods_list", [])

            for item in items:
                if str(item.get("goods_id")) == str(goods_id):
                    return {
                        "goods_id": goods_id,
                        "goods_sign": item.get("goods_sign"),
                        "goods_name": item.get("goods_name"),
                    }

            return None
        except Exception as e:
            logger.warning(f"通过goods_id搜索失败: {e}")
            return None

    async def get_product_info(self, item_id: str = None, goods_sign: str = None) -> ProductInfo:
        """获取拼多多商品信息

        Args:
            item_id: 商品ID（goods_id）
            goods_sign: 商品签名（优先使用）
        """
        try:
            # 调用拼多多商品详情API
            # 新版API使用 goods_sign 替代 goods_id_list
            params = {}

            if goods_sign:
                params["goods_sign"] = goods_sign
            elif item_id:
                # 如果没有 goods_sign，尝试用 goods_id 搜索再获取详情
                # 这里先返回错误，建议用户使用含 goods_sign 的链接
                logger.warning("拼多多需要使用 goods_sign，建议分享商品链接而不是直接打开链接")
                # 尝试通过搜索获取
                search_result = await self.search_by_goods_id(item_id)
                if search_result and search_result.get("goods_sign"):
                    params["goods_sign"] = search_result["goods_sign"]
                else:
                    raise ProductNotFoundError(f"无法获取商品签名: {item_id}")
            else:
                raise ProductNotFoundError("缺少商品ID或商品签名")

            # 添加pid
            if self.pid:
                params["pid"] = self.pid

            result = await self._call_api(
                "pdd.ddk.goods.detail",
                params
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
                # 尝试转链获取推广链接
                promotion_link = await self.convert_link(item_id, "", goods_sign)
                if promotion_link:
                    product.promotion_link = promotion_link
            except Exception as e:
                logger.warning(f"获取拼多多推广链接失败: {e}")
                # 降级：使用拼接链接
                product.promotion_link = f"https://mobile.yangkeduo.com/duo_coupon_landing.html?goods_id={item_id}&pid={self.pid}&goods_sign={goods_sign}"

            return product

        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取拼多多商品信息失败: {e}")
            raise APIError(f"获取商品信息失败: {str(e)}", platform="pdd")

    async def convert_link(self, item_id: str, original_link: str, goods_sign: str = None) -> str:
        """转换拼多多链接为推广链接

        Args:
            item_id: 商品ID
            original_link: 原始链接
            goods_sign: 商品签名（优先使用）
        """
        if not self.pid:
            raise LinkConvertError("拼多多推广位ID未配置")

        try:
            # 构建请求参数
            # 注意：拼多多签名要求参数按照字母顺序排序
            # goods_sign 和 p_id 是必须的
            actual_goods_sign = goods_sign

            if not actual_goods_sign:
                # 尝试通过搜索获取 goods_sign
                search_result = await self.search_by_goods_id(item_id)
                if search_result and search_result.get("goods_sign"):
                    actual_goods_sign = search_result["goods_sign"]
                else:
                    logger.warning(f"无法获取商品签名，转链可能失败: {item_id}")
                    # 降级返回原始链接
                    return original_link or f"https://mobile.yangkeduo.com/goods.html?goods_id={item_id}"

            # 调用转链接口生成推广链接
            params = {
                "goods_sign_list": f'["{actual_goods_sign}"]',
                "p_id": self.pid,
            }

            result = await self._call_api(
                "pdd.ddk.goods.promotion.url.generate",
                params
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
            # 降级：返回拼接的推广链接
            return f"https://mobile.yangkeduo.com/duo_coupon_landing.html?goods_id={item_id}&pid={self.pid}&goods_sign={actual_goods_sign}"

    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        """搜索拼多多商品"""
        try:
            # 拼多多搜索需要pid参数
            if not self.pid:
                raise APIError("拼多多PID未配置", platform="pdd")

            # 拼多多API要求 page_size 必须在 10-100 之间
            actual_page_size = max(10, min(100, page_size))

            result = await self._call_api(
                "pdd.ddk.goods.search",
                {
                    "keyword": keyword,
                    "page": page,
                    "page_size": actual_page_size,
                    "sort_type": 6,  # 按佣金比例排序
                    "pid": self.pid,
                }
            )

            data = result.get("goods_search_response", {})
            items = data.get("goods_list", [])

            products = []
            for item in items:
                min_group_price = Decimal(str(item.get("min_group_price", 0))) / 100
                coupon_discount = Decimal(str(item.get("coupon_discount", 0))) / 100

                goods_id = str(item.get("goods_id", ""))
                goods_sign = item.get("goods_sign", "")

                product = ProductInfo(
                    platform=PlatformType.PDD,
                    item_id=goods_id,
                    title=item.get("goods_name", ""),
                    current_price=min_group_price,
                    product_image=item.get("goods_thumbnail_url", ""),
                    shop_name=item.get("mall_name", ""),
                    commission_rate=Decimal(str(item.get("promotion_rate", 0))) / 1000 if item.get("promotion_rate") else None,
                    promotion_link=f"https://mobile.yangkeduo.com/duo_coupon_landing.html?goods_id={goods_id}&pid={self.pid}&goods_sign={goods_sign}" if goods_sign else None,
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

    async def check_authority(self) -> dict:
        """
        查询 PID 是否已绑定备案
        接口: pdd.ddk.member.authority.query
        """
        try:
            import json
            # pdd.ddk.member.authority.query 使用 pid（不是 p_id_list）
            params = {
                "pid": self.pid,
                "custom_parameters": json.dumps({"uid": "wechat_bot"}),
            }

            result = await self._call_api(
                "pdd.ddk.member.authority.query",
                params
            )

            data = result.get("authority_query_response", {})
            # 返回的是列表，取第一个
            auth_list = data.get("authority_query_list", [])
            if auth_list:
                first = auth_list[0]
                return {
                    "bind": first.get("bind", 0),  # 1:已绑定, 0:未绑定
                    "message": first.get("message", ""),
                }
            return {"bind": 0, "message": "无备案数据"}
        except Exception as e:
            logger.warning(f"查询备案状态失败: {e}")
            return {"bind": 0, "message": str(e)}

    async def generate_rp_url(self) -> str:
        """
        生成备案链接
        接口: pdd.ddk.rp.prom.url.generate
        channel_type=10 表示小程序/公众号等场景
        """
        try:
            import json
            # 使用 p_id_list 而不是 pid
            params = {
                "channel_type": 10,  # 10:小程序/公众号
                "p_id_list": f'["{self.pid}"]'
            }

            result = await self._call_api(
                "pdd.ddk.rp.prom.url.generate",
                params
            )

            data = result.get("rp_prom_url_generate_response", {})
            url_list = data.get("url_list", [])

            if url_list:
                return url_list[0].get("url", "")

            return ""
        except Exception as e:
            logger.warning(f"生成备案链接失败: {e}")
            return ""

    async def generate_pid(self, number: int = 1, pid_name: str = "公众号推广位") -> list:
        """
        创建多多进宝推广位
        接口: pdd.ddk.goods.pid.generate

        Args:
            number: 要生成的推广位数量（默认1）
            pid_name: 推广位名称

        Returns:
            生成的PID列表
        """
        try:
            params = {
                "number": number,
                "p_id_name": pid_name,
            }

            result = await self._call_api(
                "pdd.ddk.goods.pid.generate",
                params
            )

            data = result.get("p_id_generate_response", {})
            pid_list = data.get("p_id_list", [])

            logger.info(f"成功创建推广位: {pid_list}")
            return pid_list
        except Exception as e:
            logger.warning(f"创建推广位失败: {e}")
            return []