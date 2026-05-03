"""
应用配置
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    应用配置类
    从环境变量读取配置
    """

    # 应用配置
    APP_NAME: str = "price-compare-bot"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 微信配置
    WECHAT_TOKEN: str = ""                    # 公众号Token
    WECHAT_APPID: Optional[str] = None        # 公众号AppID
    WECHAT_APPSECRET: Optional[str] = None    # 公众号AppSecret
    WECHAT_ENCODING_AES_KEY: Optional[str] = None  # 消息加密密钥（可选）

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None

    # 缓存配置
    CACHE_TTL_PRODUCT: int = 3600      # 商品缓存1小时
    CACHE_TTL_SEARCH: int = 1800       # 搜索缓存30分钟
    CACHE_TTL_LINK: int = 7200         # 转链缓存2小时

    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 10    # 每分钟最多10次请求

    # 淘宝客配置
    TAOBAO_APP_KEY: Optional[str] = None
    TAOBAO_APP_SECRET: Optional[str] = None
    TAOBAO_ADZONE_ID: Optional[str] = None      # 推广位ID
    TAOBAO_SITE_ID: Optional[str] = None        # 媒体ID
    TAOBAO_SESSION: Optional[str] = None        # OAuth授权session（SC接口需要）

    # 京东联盟配置
    JD_APP_KEY: Optional[str] = None
    JD_APP_SECRET: Optional[str] = None
    JD_UNION_ID: Optional[str] = None           # 联盟ID
    JD_POSITION_ID: Optional[str] = None        # 推广位ID

    # 拼多多配置
    PDD_CLIENT_ID: Optional[str] = None
    PDD_CLIENT_SECRET: Optional[str] = None
    PDD_PID: Optional[str] = None               # 推广位ID

    # 日志配置
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
