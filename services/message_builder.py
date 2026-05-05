"""
消息组装服务
生成微信回复消息
"""
from decimal import Decimal
from typing import List, Optional, Union

from models import ProductInfo, PlatformType
from config.content_config import WallpaperItem, RiddleItem
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
        构建帮助消息（带人设）
        """
        help_text = """🤖 小芸生活助手

嗨！我是小芸，你的省钱小帮手~ 🎀

【💰 查优惠券】
发送商品链接，自动查找隐藏优惠券

【🔍 搜好物】
发送商品名称，如：iPhone 15、洗衣液

💡 小贴士：
• 淘宝/京东接口接入中，敬请期待
• 优惠券数量有限，看到好价赶紧入手哦！
• 还有更多隐藏玩法等你挖掘哦！

有任何问题随时找我~ 😊"""

        return cls.build_text_message(help_text)

    @classmethod
    def build_hot_keywords_message(cls, keywords: list) -> dict:
        """
        构建今日热门关键词消息（带人设）
        """
        if not keywords:
            return cls.build_text_message(
                "🔥 今日热门榜单\n\n"
                "暂无搜索数据，快来成为第一个！\n\n"
                "发送商品名称（如：洗衣液）\n"
                "或商品链接开始查券~"
            )

        lines = ["🔥 今日大家都在买什么\n"]
        lines.append("（实时更新，跟着买不踩坑）\n")

        for i, (keyword, count) in enumerate(keywords, 1):
            if i == 1:
                emoji = "🥇"
            elif i == 2:
                emoji = "🥈"
            elif i == 3:
                emoji = "🥉"
            else:
                emoji = f"{i}."

            lines.append(f"{emoji} {keyword}")

        lines.append("\n💡 发送以上关键词或任意商品名称")
        lines.append("小芸帮你找隐藏优惠券~")

        return cls.build_text_message("\n".join(lines))

    @classmethod
    def _build_description(cls, product: ProductInfo) -> str:
        """构建商品描述（精简版，适合微信图文）"""
        lines = []

        platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")

        if product.coupon and product.coupon.amount > 0:
            # 有优惠券时：
            # 第一行：原价
            if product.original_price and product.original_price > product.current_price:
                lines.append(f"💰原价¥{product.original_price}")
            else:
                lines.append(f"💰原价¥{product.current_price}")
            # 第二行：券后价
            lines.append(f"🔥券后¥{product.final_price}")
            # 第三行：行动号召
            lines.append("👉点击卡片领券购买")
        else:
            # 无优惠券时：
            # 第一行：现价
            lines.append(f"💰现价¥{product.current_price}")
            # 第二行：平台标识
            lines.append(f"{platform_icon}精选好物")
            # 第三行：行动号召
            lines.append("👉点击卡片立即购买")

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

    # ========== 模块二：人设包装消息构建 ==========

    @classmethod
    def build_product_message_with_persona(cls, product: ProductInfo) -> dict:
        """
        构建带人设文案的商品卡片
        """
        platform_icon = cls.PLATFORM_ICONS.get(product.platform, "🛒")
        title = f"{platform_icon} {cls._truncate(product.title, 30)}"
        description = cls._build_description(product)

        # 在描述前添加人设话术
        persona_intro = "✨ 小芸帮你找到隐藏优惠！\n\n"
        description = persona_intro + description

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
    def build_search_comparison_message(cls, keyword: str, products: list) -> dict:
        """
        构建搜索对比消息（文本+HTML链接）
        让用户货比三家
        """
        if not products:
            return cls.build_text_message(f'未找到 "{keyword}" 的相关商品')

        lines = [
            f"🔍 关于【{keyword}】，小芸帮你找到这几个高性价比的：\n"
        ]

        for i, p in enumerate(products, 1):
            platform_icon = cls.PLATFORM_ICONS.get(p.platform, "🛒")
            price_str = f"¥{p.final_price}"

            # 标记最低价
            tag = "【推荐】" if i == 1 else ""

            # 标记优惠券
            coupon_str = f" 省¥{p.coupon.amount}" if p.coupon else ""

            # 使用HTML超链接格式
            link_url = p.promotion_link or p.product_url or "#"

            lines.append(f"{i}. {tag}{cls._truncate(p.title, 18)}")
            lines.append(f"   💰 {price_str}{coupon_str}")
            # 微信支持的HTML链接格式
            lines.append(f'   <a href="{link_url}">👉点击查看详情</a>')
            lines.append("")

        lines.append("💡 点击蓝字查看商品详情")
        lines.append("有问题随时找小芸~ 😊")

        # 使用HTML格式返回（微信支持<a>标签）
        return {
            "type": "text",
            "content": "\n".join(lines),
        }

    @classmethod
    def build_wallpaper_message(cls, wallpaper) -> dict:
        """
        构建壁纸消息
        """
        return {
            "type": "news",
            "article_count": 1,
            "articles": [{
                "title": f"🎨 {wallpaper.title}",
                "description": f"{wallpaper.description}\n💕 每日更新精美壁纸\n👉点击领取原图",
                "pic_url": wallpaper.image_url,
                "url": wallpaper.pan_url,
            }]
        }

    @classmethod
    def build_riddle_message(cls, riddle) -> dict:
        """
        构建猜谜消息
        """
        text = f"""🎯 脑筋急转弯时间！

{riddle.question}

💡 提示：{riddle.hint if riddle.hint else "仔细想想~"}

———

🤔 想到答案了吗？
回复"答案"查看正确答案
回复"猜谜"再来一题
回复"热门"看看优惠商品"""

        return cls.build_text_message(text)

    @classmethod
    def build_riddle_answer_message(cls, riddle) -> dict:
        """
        构建猜谜答案消息
        """
        text = f"""✨ 揭晓答案！

{riddle.question}

🎉 正确答案：{riddle.answer}

———

还想继续玩吗？
回复"猜谜"再来一题
回复"壁纸"领取精美壁纸
回复"热门"查看优惠商品"""

        return cls.build_text_message(text)

    @classmethod
    def build_traffic_card_message(cls, config: dict) -> dict:
        """
        构建流量卡推广消息
        """
        return {
            "type": "news",
            "article_count": 1,
            "articles": [{
                "title": config["title"],
                "description": config["description"],
                "pic_url": config["image_url"],
                "url": config["promotion_url"],
            }]
        }
