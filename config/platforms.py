"""
平台配置
定义各平台的域名、链接规则等
"""
from dataclasses import dataclass
from typing import List, Pattern
import re


@dataclass
class PlatformConfig:
    """平台配置"""
    name: str                          # 平台名称
    code: str                          # 平台代码
    icon: str                          # 平台图标
    domains: List[str]                 # 支持的域名
    item_id_patterns: List[Pattern]    # 商品ID提取正则
    short_link_domains: List[str]      # 短链接域名
    max_coupon_amount: int = 0         # 最大优惠券金额（用于显示）
    affiliate_enabled: bool = True     # 是否支持转链


# 淘宝配置
TAOBAO_CONFIG = PlatformConfig(
    name="淘宝",
    code="taobao",
    icon="🍑",
    domains=[
        "taobao.com",
        "tmall.com",
        "tb.cn",
    ],
    item_id_patterns=[
        re.compile(r"[?&]id=(\d+)"),           # 标准链接 ?id=123
        re.compile(r"/item/(\d+)"),           # 路由格式 /item/123
        re.compile(r"itemId:\s*'(\d+)'"),     # JS格式
    ],
    short_link_domains=["m.tb.cn", "s.click.taobao.com"],
    max_coupon_amount=1000,
)

# 京东配置
JD_CONFIG = PlatformConfig(
    name="京东",
    code="jd",
    icon="🐕",
    domains=[
        "jd.com",
        "jingxi.com",
        "3.cn",
    ],
    item_id_patterns=[
        re.compile(r"/(\d+)\.html"),          # /123456.html
        re.compile(r"skuId[=:](\d+)"),        # skuId=123 或 skuId:123
    ],
    short_link_domains=["3.cn", "u.jd.com"],
    max_coupon_amount=500,
)

# 拼多多配置
PDD_CONFIG = PlatformConfig(
    name="拼多多",
    code="pdd",
    icon="🔴",
    domains=[
        "pinduoduo.com",
        "yangkeduo.com",
        "pddpic.com",
    ],
    item_id_patterns=[
        re.compile(r"goods_id[=:](\d+)"),     # goods_id=123
    ],
    short_link_domains=["p.pinduoduo.com"],
    max_coupon_amount=200,
)

# 平台配置映射
PLATFORM_CONFIGS = {
    "taobao": TAOBAO_CONFIG,
    "jd": JD_CONFIG,
    "pdd": PDD_CONFIG,
}


def get_platform_config(code: str) -> PlatformConfig:
    """获取平台配置"""
    return PLATFORM_CONFIGS.get(code)
