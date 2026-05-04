"""
内容配置
壁纸、猜谜、流量卡等互动内容配置
"""
from typing import List, Dict
from dataclasses import dataclass


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
    "title": "📱 超值流量卡",
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
SPECIAL_COMMANDS = {
    "壁纸": ["壁纸", "wallpaper", "背景图", "手机壁纸"],
    "猜谜": ["猜谜", "脑筋急转弯", "谜语", "答题", "riddle"],
    "流量卡": ["流量卡", "流量", "手机卡", "电话卡", "大流量"],
    "热门": ["热门", "今日热门", "hot", "排行榜"],
    "帮助": ["帮助", "help", "菜单", "menu", "怎么用"],
}


def get_random_wallpaper() -> WallpaperItem:
    """随机获取一张壁纸"""
    import random
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

    Returns:
        指令类型或None
    """
    text_lower = text.lower().strip()

    for command_type, keywords in SPECIAL_COMMANDS.items():
        if text_lower in keywords:
            return command_type

    return None
