"""
口令解析服务
解析淘宝/京东/拼多多口令，提取真实链接
"""
import re
from typing import Optional
from urllib.parse import unquote

import httpx
from loguru import logger


class KoulingParser:
    """
    口令解析器

    口令格式示例：
    - 淘宝：￥ABC123￥、€DEF456€
    - 京东：(ABC123)
    - 拼多多：一般直接是链接
    """

    # 口令正则表达式
    # 匹配被特殊字符包围的字母数字组合
    KOULING_PATTERNS = [
        r'[￥€¢£¥]([a-zA-Z0-9]{8,12})[￥€¢£¥]',  # 淘宝标准口令
        r'\(([a-zA-Z0-9]{8,12})\)',              # 京东口令
        r'【([^【】]+)】',                        # 带描述的口令
    ]

    @classmethod
    def extract_kouling(cls, text: str) -> Optional[str]:
        """
        从文本中提取口令

        Args:
            text: 用户输入文本

        Returns:
            提取到的口令字符串，如果没有返回None
        """
        for pattern in cls.KOULING_PATTERNS:
            match = re.search(pattern, text)
            if match:
                kouling = match.group(0)  # 包含符号的完整口令
                logger.info(f"提取到口令: {kouling}")
                return kouling
        return None

    @classmethod
    async def parse_kouling(cls, kouling: str) -> Optional[str]:
        """
        解析口令，返回真实链接

        Args:
            kouling: 口令字符串

        Returns:
            真实商品链接
        """
        # 目前口令解析需要调用各平台的API或解码服务
        # 这里提供基础实现，实际可能需要接入第三方解码服务

        # 方案1：如果是包含链接的文本，直接提取链接
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, kouling)
        if urls:
            return urls[0]

        # 方案2：调用淘宝开放平台的口令解析API
        # 需要申请 taobao.wireless.share.tpwd.query 权限
        # 这里先返回None，表示无法解析

        logger.warning(f"暂不支持解析口令: {kouling}")
        return None

    @classmethod
    def is_kouling(cls, text: str) -> bool:
        """
        判断文本是否包含口令

        Args:
            text: 待检查文本

        Returns:
            True 如果包含口令
        """
        for pattern in cls.KOULING_PATTERNS:
            if re.search(pattern, text):
                return True
        return False


async def extract_and_parse_kouling(text: str) -> Optional[str]:
    """
    从文本中提取并解析口令

    Args:
        text: 用户输入

    Returns:
        解析出的真实链接，如果没有返回None
    """
    # 提取口令
    kouling = KoulingParser.extract_kouling(text)
    if not kouling:
        return None

    # 解析口令
    url = await KoulingParser.parse_kouling(kouling)
    return url
