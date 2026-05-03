"""
意图识别服务
判断用户输入是商品搜索还是闲聊
"""
import re
from typing import List


class IntentClassifier:
    """
    简单的意图识别器
    基于规则和关键词判断用户意图
    """

    # 常见问候语/闲聊词汇（不应触发搜索）
    GREETINGS = {
        "你好", "您好", "在吗", "在嘛", "有人吗", "哈喽", "嗨", "hello", "hi",
        "谢谢", "感谢", "多谢", "拜拜", "再见", "goodbye", "bye",
        "早上好", "中午好", "晚上好", "晚安",
        "请问", "咨询一下", "问一下",
        "辛苦了", "麻烦你了", "打扰了",
    }

    # 常见疑问词开头（可能不是商品）
    QUESTION_PREFIXES = [
        "怎么", "如何", "为什么", "什么", "多少", "哪里", "在哪",
        "能", "可以", "会", "有没", "是不是", "对吗",
    ]

    # 商品特征词（有助于判断是商品）
    PRODUCT_INDICATORS = [
        "手机", "电脑", "笔记本", "平板", "耳机", "手表",
        "衣服", "裤子", "鞋子", "包包", "袜子", "内衣",
        "零食", "食品", "饮料", "水果", "蔬菜", "大米", "油",
        "洗发水", "沐浴露", "牙膏", "纸巾", "洗衣液",
        "iPhone", "iPad", "Mac", "华为", "小米", "苹果",
        "华为", "小米", "OPPO", "vivo", "三星",
        "￥", "元", "块", "折扣", "优惠", "便宜",
    ]

    @classmethod
    def is_likely_product_keyword(cls, text: str) -> bool:
        """
        判断文本是否可能是商品关键词

        Args:
            text: 用户输入文本

        Returns:
            True 如果是可能的商品关键词
        """
        if not text:
            return False

        text = text.strip()
        text_lower = text.lower()

        # 1. 长度检查（商品名通常在2-15字之间）
        if len(text) < 2 or len(text) > 15:
            return False

        # 2. 排除纯数字（可能是误触）
        if text.isdigit():
            return False

        # 3. 排除问候语
        if text_lower in cls.GREETINGS:
            return False

        # 4. 排除以疑问词开头的长句
        for prefix in cls.QUESTION_PREFIXES:
            if text.startswith(prefix) and len(text) > 6:
                return False

        # 5. 检查是否包含商品特征词（有的话直接认为是商品）
        for indicator in cls.PRODUCT_INDICATORS:
            if indicator.lower() in text_lower:
                return True

        # 6. 包含数字或英文（可能是型号，如 iPhone15、Mate60）
        if re.search(r'[0-9a-zA-Z]', text):
            # 但不包含过多标点
            if text.count('。') <= 1 and text.count('，') <= 1:
                return True

        # 7. 纯中文（2-6字）也可能是商品名
        if re.match(r'^[一-龥]+$', text) and 2 <= len(text) <= 6:
            return True

        return False

    @classmethod
    def get_fallback_response(cls, text: str) -> str:
        """
        当不认为是商品搜索时，返回引导语

        Args:
            text: 用户输入

        Returns:
            引导回复文本
        """
        if len(text) > 15:
            return "搜索内容太长了，请简短描述商品名称~\n\n例如：iPhone 15、洗衣液、纸巾"

        if text in cls.GREETINGS or len(text) <= 3:
            return """你好！我是省钱助手 🤖

可以帮你：
• 🔍 查优惠券：发送商品链接
• 🛒 搜商品：发送商品名称
• 🔥 看热门：发送"热门"

想买点什么呢？"""

        if text.isdigit():
            return "看起来是个数字，请发送商品名称开始搜索~"

        return """不太确定你想搜索什么商品~

试试发送：
• 具体商品名（如：iPhone 15、洗衣液）
• 商品链接（自动查询优惠券）
• "热门"查看大家都在买什么

需要帮忙随时告诉我！"""
