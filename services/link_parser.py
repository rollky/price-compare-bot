"""
链接解析服务
识别平台并提取商品ID
"""
from typing import Optional, Tuple
from urllib.parse import urlparse

from models import PlatformType
from config import get_settings, PLATFORM_CONFIGS
from platforms import ADAPTERS
from core.exceptions import ParseError
from core.logger import logger


class LinkParser:
    """
    链接解析服务

    负责识别链接所属平台，并调用对应适配器解析商品ID
    """

    def __init__(self):
        self.adapters = {}
        self._init_adapters()

    def _init_adapters(self):
        """初始化所有平台适配器"""
        for code, adapter_class in ADAPTERS.items():
            config = PLATFORM_CONFIGS.get(code)
            if config:
                self.adapters[code] = adapter_class(config)

    async def parse(self, link: str) -> Tuple[Optional[PlatformType], Optional[str]]:
        """
        解析链接，返回平台和商品ID

        Args:
            link: 待解析的链接

        Returns:
            (平台类型, 商品ID)，如果无法解析则返回 (None, None)
        """
        if not link or not link.startswith("http"):
            return None, None

        # 清理链接（移除跟踪参数）
        cleaned_link = self._clean_link(link)

        # 尝试匹配各平台
        for code, adapter in self.adapters.items():
            try:
                if await adapter.is_valid_link(cleaned_link):
                    item_id = await adapter.parse_link(cleaned_link)
                    if item_id:
                        platform = PlatformType(code)
                        logger.info(f"链接解析成功: {platform.value} - {item_id}")
                        return platform, item_id
            except Exception as e:
                logger.warning(f"解析{code}链接失败: {e}")
                continue

        logger.warning(f"无法识别链接: {link[:100]}")
        return None, None

    async def identify_platform(self, link: str) -> Optional[PlatformType]:
        """
        仅识别链接所属平台，不解析商品ID

        Args:
            link: 待识别的链接

        Returns:
            平台类型，如果无法识别返回None
        """
        if not link:
            return None

        link_lower = link.lower()

        for code, adapter in self.adapters.items():
            if await adapter.is_valid_link(link_lower):
                return PlatformType(code)

        return None

    def _clean_link(self, link: str) -> str:
        """
        清理链接中的跟踪参数

        Args:
            link: 原始链接

        Returns:
            清理后的链接
        """
        # 移除常见的跟踪参数
        tracking_params = [
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "spm", "source", "from", "refer", "ref",
        ]

        try:
            parsed = urlparse(link)
            # 保留scheme, netloc, path, query中与跟踪无关的部分
            # 简化处理：直接返回原链接，实际解析时由各适配器处理
            return link
        except Exception:
            return link

    def is_short_link(self, link: str) -> bool:
        """
        判断是否为短链接

        Args:
            link: 待检查的链接

        Returns:
            True如果是短链接
        """
        link_lower = link.lower()

        short_domains = [
            "tb.cn", "s.click.taobao.com",
            "3.cn", "u.jd.com",
            "p.pinduoduo.com",
        ]

        return any(domain in link_lower for domain in short_domains)
