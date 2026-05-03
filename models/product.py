"""
商品数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List


class PlatformType(str, Enum):
    """平台类型"""
    TAOBAO = "taobao"
    JD = "jd"
    PDD = "pdd"
    UNKNOWN = "unknown"


@dataclass
class CouponInfo:
    """优惠券信息"""
    amount: Decimal  # 优惠金额
    threshold: Decimal  # 使用门槛（满多少可用）
    title: str  # 优惠券标题
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    link: str = ""  # 领券链接


@dataclass
class ProductInfo:
    """
    商品信息（统一数据结构）

    所有平台查询结果都转换为这个结构，保证上层处理逻辑统一
    """
    # 基础信息
    platform: PlatformType
    item_id: str
    title: str

    # 价格信息
    current_price: Decimal  # 当前售价
    original_price: Optional[Decimal] = None  # 原价（划线价）

    # 优惠券
    coupon: Optional[CouponInfo] = None

    # 计算后的价格
    @property
    def final_price(self) -> Decimal:
        """券后价"""
        if self.coupon:
            return self.current_price - self.coupon.amount
        return self.current_price

    @property
    def discount_rate(self) -> float:
        """折扣率（0-1之间）"""
        if self.original_price and self.original_price > 0:
            return float(self.final_price / self.original_price)
        return 1.0

    # 推广信息
    commission_rate: Optional[Decimal] = None  # 佣金比例（如 0.05 表示5%）
    promotion_link: str = ""  # 推广链接

    # 商品详情
    product_image: str = ""  # 主图URL
    product_url: str = ""  # 商品原始链接
    shop_name: str = ""  # 店铺名
    sales_count: Optional[int] = None  # 销量

    # 评价信息
    rating: Optional[float] = None  # 评分（0-5）
    rating_count: Optional[int] = None  # 评价数量

    # 元信息
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转换为字典（用于缓存序列化）"""
        return {
            "platform": self.platform.value,
            "item_id": self.item_id,
            "title": self.title,
            "current_price": str(self.current_price),
            "original_price": str(self.original_price) if self.original_price else None,
            "coupon": {
                "amount": str(self.coupon.amount),
                "threshold": str(self.coupon.threshold),
                "title": self.coupon.title,
                "link": self.coupon.link,
            } if self.coupon else None,
            "final_price": str(self.final_price),
            "commission_rate": str(self.commission_rate) if self.commission_rate else None,
            "promotion_link": self.promotion_link,
            "product_image": self.product_image,
            "shop_name": self.shop_name,
            "sales_count": self.sales_count,
            "rating": self.rating,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PriceHistory:
    """价格历史记录"""
    item_id: str
    platform: PlatformType
    prices: List[tuple] = field(default_factory=list)  # [(datetime, Decimal), ...]

    def get_lowest_price(self, days: int = 30) -> Optional[Decimal]:
        """获取最近N天最低价"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        recent_prices = [p for t, p in self.prices if t > cutoff]
        return min(recent_prices) if recent_prices else None

    def get_average_price(self, days: int = 30) -> Optional[Decimal]:
        """获取最近N天平均价"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        recent_prices = [p for t, p in self.prices if t > cutoff]
        if not recent_prices:
            return None
        return sum(recent_prices) / len(recent_prices)


@dataclass
class SearchResult:
    """搜索结果"""
    keyword: str
    products: List[ProductInfo] = field(default_factory=list)
    total: int = 0
    platform: Optional[PlatformType] = None
