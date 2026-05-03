"""
消息组装服务
生成微信回复消息
"""
from decimal import Decimal
from typing import List, Optional

from models import ProductInfo, PlatformType
from core.logger import logger


class MessageBuilder:
    """
    消息组装服务

    将商品信息组装成微信图文消息格式
    """

    # 平台图标映射
    PLATFORM_ICONS = {
        PlatformType.TAOBAO: "🍑",
        PlatformType.JD: "🐕",
        PlatformType.PDD: "🔴",
    }

    @classmethod
    def build_product_message(cls, product: ProductInfo) -> dict:
        """
        构建单个商品的回复消息（图文消息）
        """
        platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")
        title = f"{platform_icon} {cls._truncate(product.title, 30)}"
        description = cls._build_description(product)

        return {
            "type": "news",
            "article_count": 1,
            "articles": [{
                "title": title,
                "description": description,
                "pic_url": product.product_image,
                "url": product.promotion_link or product.product_url,
            }]
        }

    @classmethod
    def build_search_summary_message(cls, products: List[ProductInfo], keyword: str) -> dict:
        """
        构建搜索结果汇总卡片（多商品对比）
        """
        if not products:
            return cls.build_text_message(f'未找到 "{keyword}" 的相关商品')

        # 按价格排序
        sorted_products = sorted(products, key=lambda x: x.final_price)
        cheapest = sorted_products[0]

        # 构建标题
        title = f"🔍 {keyword} 找到 {len(products)} 个优惠"

        # 构建描述 - 列出所有商品
        lines = [f"为您找到 {len(products)} 个商品：\n"]

        for i, p in enumerate(sorted_products[:5], 1):  # 最多显示5个
            platform_icon = cls.PLATFORM_ICONS.get(p.platform, "🛒")
            price_str = f"¥{p.final_price}"

            # 标记最低价
            if i == 1:
                price_str += " ✅最低"

            # 标记优惠券
            coupon_str = f" (券¥{p.coupon.amount})" if p.coupon else ""

            lines.append(f"{i}. {platform_icon} {cls._truncate(p.title, 15)}")
            lines.append(f"   价格：{price_str}{coupon_str}")
            lines.append("")

        lines.append(f"👆 点击卡片查看【{cheapest.title[:15]}...】")

        description = "\n".join(lines)

        return {
            "type": "news",
            "article_count": 1,
            "articles": [{
                "title": title,
                "description": description,
                "pic_url": cheapest.product_image,
                "url": cheapest.promotion_link or cheapest.product_url,
            }]
        }

    @classmethod
    def build_comparison_message(cls, products: List[ProductInfo]) -> dict:
        """
        构建比价结果消息

        Args:
            products: 各平台的商品列表

        Returns:
            微信图文消息字典
        """
        if not products:
            return cls.build_text_message("未找到相关商品")

        # 找出最低价
        cheapest = min(products, key=lambda x: x.final_price)

        # 构建标题
        title = f"🔍 找到 {len(products)} 个平台的价格"

        # 构建描述
        description_lines = ["多平台比价结果：\n"]

        for product in products:
            platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")
            price_str = f"¥{product.final_price}"

            if product.final_price == cheapest.final_price:
                price_str += " ✅最低"

            coupon_str = ""
            if product.coupon:
                coupon_str = f" (券¥{product.coupon.amount})"

            line = f"{platform_icon} {product.platform.value}: {price_str}{coupon_str}"
            description_lines.append(line)

        description_lines.append(f"\n👆 点击查看详情")

        description = "\n".join(description_lines)

        # 使用最低价的商品作为主商品
        return {
            "type": "news",
            "article_count": 1,
            "articles": [{
                "title": title,
                "description": description,
                "pic_url": cheapest.product_image,
                "url": cheapest.promotion_link or cheapest.product_url,
            }]
        }

    @classmethod
    def build_search_result_message(cls, keyword: str, products: List[ProductInfo]) -> dict:
        """
        构建搜索结果消息

        Args:
            keyword: 搜索关键词
            products: 商品列表

        Returns:
            微信图文消息字典
        """
        if not products:
            return cls.build_text_message(f'未找到 "{keyword}" 的相关商品')

        # 只取前3个结果
        top_products = products[:3]
        count = len(products)

        if len(top_products) == 1:
            # 只有一个结果，显示详细信息
            return cls.build_product_message(top_products[0])

        # 多个结果，使用多图文消息
        articles = []
        for i, product in enumerate(top_products):
            platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")

            title = f"{platform_icon} {cls._truncate(product.title, 30)}"
            if product.coupon:
                title += f" 省¥{product.coupon.amount}"

            description = cls._build_simple_description(product)

            articles.append({
                "title": title,
                "description": description,
                "pic_url": product.product_image,
                "url": product.promotion_link or product.product_url,
            })

        return {
            "type": "news",
            "article_count": len(articles),
            "articles": articles,
        }

    @classmethod
    def build_multi_platform_message(cls, products: List[ProductInfo]) -> dict:
        """
        构建多平台多图文消息（每个平台一个卡片）

        Args:
            products: 各平台的商品列表

        Returns:
            多图文消息字典
        """
        if not products:
            return cls.build_text_message("未找到相关商品")

        articles = []
        for product in products:
            platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")

            title = f"{platform_icon} {cls._truncate(product.title, 30)}"
            if product.coupon:
                title += f" 省¥{product.coupon.amount}"

            description = cls._build_simple_description(product)

            articles.append({
                "title": title,
                "description": description,
                "pic_url": product.product_image,
                "url": product.promotion_link or product.product_url,
            })

        logger.info(f"构建多图文消息: {len(articles)} 条图文")

        return {
            "type": "news",
            "article_count": len(articles),
            "articles": articles,
        }

    @classmethod
    def build_text_message(cls, text: str) -> dict:
        """
        构建纯文本消息

        Args:
            text: 消息内容

        Returns:
            文本消息字典
        """
        return {
            "type": "text",
            "content": text,
        }

    @classmethod
    def build_help_message(cls) -> dict:
        """
        构建帮助消息

        Returns:
            帮助文本消息
        """
        help_text = """🤖 省钱助手使用指南

【查价格】
直接发送商品链接，自动查询优惠券和佣金

【搜商品】
发送关键词，如：iPhone 15

【支持平台】
🔴 拼多多

💡 提示：
• 优惠券有时效，请尽快使用
• 淘宝/京东接入中，敬请期待

如有问题，请联系客服"""

        return cls.build_text_message(help_text)

    @classmethod
    def _build_description(cls, product: ProductInfo) -> str:
        """构建商品描述（精简版，适合微信图文）"""
        lines = []


        # 第一行：优惠券信息
        if product.coupon and product.coupon.amount > 0:
            lines.append(f"🎫优惠券¥{product.coupon.amount}")

        # 第二行：原价 vs 现价
        if product.original_price and product.original_price > product.current_price:
            lines.append(f"💰原价¥{product.original_price} 🔥现价¥{product.current_price}")
        else:
            lines.append(f"🔥现价¥{product.current_price}")

        # 第二行：销量+平台
        platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")
        if product.sales_count:
            sales_str = cls._format_number(product.sales_count)
            lines.append(f"📈销量{sales_str} {platform_icon}{product.platform.value}")
        else:
            lines.append(f"{platform_icon}{product.platform.value} 精选好物")

        # 第三行：行动号召
        lines.append("👉点击卡片领券购买")

        return "\n".join(lines)

    @classmethod
    def _build_simple_description(cls, product: ProductInfo) -> str:
        """构建简洁描述（用于多图文）"""
        lines = []

        lines.append(f"价格：¥{product.final_price}")

        if product.coupon:
            lines.append(f"优惠券：{product.coupon.title}")

        if product.sales_count:
            lines.append(f"销量：{cls._format_number(product.sales_count)}")

        return "\n".join(lines)

    @classmethod
    def _generate_advice(cls, product: ProductInfo) -> str:
        """生成购买建议"""
        if not product.coupon:
            return "当前价格稳定，可入手"

        # 根据优惠力度生成建议
        if product.discount_rate <= 0.7:
            return "🔥 超值优惠，建议立即购买！"
        elif product.discount_rate <= 0.85:
            return "近期好价，可以考虑入手"
        elif product.coupon:
            return "有优惠券可用，别忘了领券"

        return ""

    @classmethod
    def _truncate(cls, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    @classmethod
    def _format_number(cls, num: int) -> str:
        """格式化数字"""
        if num >= 10000:
            return f"{num / 10000:.1f}万"
        elif num >= 1000:
            return f"{num / 1000:.1f}千"
        return str(num)
