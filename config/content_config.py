"""
内容配置
壁纸、猜谜、流量卡等互动内容配置
"""
import re
import random
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class WallpaperItem:
    """壁纸项"""
    title: str
    image_url: str
    pan_url: str  # 网盘链接
    description: str = ""


@dataclass
class RiddleItem:
    """猜谜题目"""
    question: str
    answer: str
    hint: str = ""  # 提示


# 壁纸库（示例数据，后续可扩展）
WALLPAPERS: List[WallpaperItem] = [
    WallpaperItem(
        title="🎀 可爱治愈系壁纸",
        image_url="https://img.pddpic.com/mms-material-img/2024-05-01/abc123.jpg",
        pan_url="https://pan.baidu.com/s/1xxx",
        description="治愈系可爱风，每天好心情~"
    ),
    WallpaperItem(
        title="✨ 简约ins风壁纸",
        image_url="https://img.pddpic.com/mms-material-img/2024-05-01/def456.jpg",
        pan_url="https://pan.baidu.com/s/1yyy",
        description="简约不简单，高级感满满"
    ),
]

# 猜谜题库
RIDDLES: List[RiddleItem] = [
    RiddleItem(
        question="🏮 什么东西越洗越脏？",
        answer="水",
        hint="想想每天用的..."
    ),
    RiddleItem(
        question="🏮 什么东西有头无脚？",
        answer="硬币",
        hint="买东西会用到..."
    ),
    RiddleItem(
        question="🏮 什么东西打破了才能吃？",
        answer="鸡蛋",
        hint="早餐常见..."
    ),
    RiddleItem(
        question="🏮 什么东西越生气越大？",
        answer="脾气",
        hint="情绪相关..."
    ),
    RiddleItem(
        question="🏮 什么东西属于你，但别人用的比你多？",
        answer="名字",
        hint="每个人都有..."
    ),
]

# 流量卡推广配置
TRAFFIC_CARD_CONFIG = {
    "title": "🔥运营商内部套餐！29元月租200G大流量，限时免费申请，手慢无！",
    "image_url": "https://img.huojukj.com/upload/20260428/RXCHnjDdzm/14882ef71d7ab081008d8fa8c84d5723.png",  # 流量卡推广图片
    "promotion_url": "https://ka.huojukj.com/?u=112233",  # 推广链接，待填写
    "description": """✅ 官方正规卡
✅ 4G/5G通用
✅ 全国可用
    
💥 点击卡片免费领取

📱 月租：19元/月
📶 流量：100G全国通用
📞 通话：100分钟


🔥 限时办理，扫码申请 """,
    "enabled": True  # 暂时未启用，等链接配置好后改为True
}


# 专属指令词库
# 注意：现在从数据库读取，这里保留作为兼容性导入
# 首次运行时会自动初始化到数据库
try:
    from models.keyword import get_keyword_manager
    _km = get_keyword_manager()
    SPECIAL_COMMANDS = _km.get_keywords_dict()
except Exception as e:
    # 数据库未初始化时的默认配置
    SPECIAL_COMMANDS = {
        "壁纸": ["壁纸", "wallpaper", "背景图", "手机壁纸"],
        "猜谜": ["猜谜", "脑筋急转弯", "谜语", "答题", "riddle"],
        "流量卡": ["流量卡", "流量", "手机卡", "电话卡", "大流量"],
        "热门": ["热门", "今日热门", "hot", "排行榜"],
        "帮助": ["帮助", "help", "菜单", "menu", "怎么用"],
    }


def get_random_wallpaper() -> Optional[WallpaperItem]:
    """
    随机获取一张壁纸
    优先从 Bing API 获取，失败时返回本地默认壁纸
    """
    logger = logging.getLogger(__name__)

    # 尝试从 Bing API 获取
    if HAS_REQUESTS:
        try:
            # Bing 壁纸 API，获取最近8天的壁纸
            url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=zh-CN"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("images"):
                # 随机选择一张
                image = random.choice(data["images"])
                base_url = image.get("urlbase", "")

                # 构造竖屏手机壁纸 URL (1080x1920)
                if base_url:
                    mobile_url = f"https://www.bing.com{base_url}_1080x1920.jpg"
                else:
                    mobile_url = "https://www.bing.com" + image.get("url", "")

                # 横屏预览图（用于微信卡片展示）
                preview_url = "https://www.bing.com" + image.get("url", "")

                # 清理版权信息中的 HTML 标签
                # copyright_text = image.get("copyright", "Bing每日精选")
                # copyright_clean = re.sub(r'<[^>]+>', '', copyright_text)
                image_title = image.get("title", "")

                return WallpaperItem(
                    title=" 每日精选壁纸",
                    image_url=preview_url,
                    pan_url=mobile_url,
                    # description=f"{copyright_clean}\n🌍 全球风景每日更新\n📱 竖屏高清，点击领取原图"
                    description=f""""
                    🌍 全球风景\n
                    ✨ {image_title}\n
                    📱 点击领取原图"
                    """
                )
        except Exception as e:
            logger.warning(f"从Bing获取壁纸失败: {e}")

    # 失败时返回本地默认壁纸
    if WALLPAPERS:
        return random.choice(WALLPAPERS)

    return None


def get_random_riddle() -> RiddleItem:
    """随机获取一个谜语"""
    import random
    if RIDDLES:
        return random.choice(RIDDLES)
    return None


# 记录当前用户的猜谜状态（简单实现，实际应该用Redis）
_user_riddles = {}


def set_user_riddle(openid: str, riddle: RiddleItem):
    """记录用户当前的谜题"""
    _user_riddles[openid] = riddle


def get_user_riddle(openid: str) -> RiddleItem:
    """获取用户当前的谜题"""
    return _user_riddles.get(openid)


def match_special_command(text: str) -> str:
    """
    匹配专属指令
    优先从数据库读取，支持动态配置

    Returns:
        指令类型或None
    """
    try:
        from models.keyword import get_keyword_manager
        manager = get_keyword_manager()
        return manager.match_command(text)
    except Exception as e:
        # 数据库失败时的降级方案
        text_lower = text.lower().strip()
        for command_type, keywords in SPECIAL_COMMANDS.items():
            if text_lower in keywords:
                return command_type
        return None
