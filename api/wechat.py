"""
微信API接口
处理微信服务器的消息推送
"""
import hashlib
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from loguru import logger

from config import get_settings
from services import LinkParser, PriceService, MessageBuilder
from services.kouling_parser import extract_and_parse_kouling, KoulingParser
from services.intent_classifier import IntentClassifier
from config.content_config import (
    match_special_command, get_random_wallpaper,
    TRAFFIC_CARD_CONFIG, WallpaperItem
)
from models import RiddleItem, get_riddle_game_manager
from models.keyword import get_keyword_manager
from services.wechat_menu import handle_menu_event
from core.exceptions import APIError, ProductNotFoundError, ParseError
from core.logger import logger as log

wechat_router = APIRouter(prefix="/wechat", tags=["wechat"])

# 初始化服务
link_parser = LinkParser()
price_service = PriceService()


def verify_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    """
    验证微信签名

    微信签名算法：
    1. 将 token、timestamp、nonce 按字典序排序
    2. 拼接成字符串
    3. SHA1加密
    4. 与signature对比
    """
    tmp_list = [token, timestamp, nonce]
    tmp_list.sort()
    tmp_str = ''.join(tmp_list)
    hashcode = hashlib.sha1(tmp_str.encode()).hexdigest()
    return hashcode == signature


@wechat_router.get("/callback")
async def wechat_verify(
    signature: str = Query(..., description="微信加密签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    echostr: str = Query(..., description="随机字符串"),
):
    """
    微信服务器验证接口
    用于配置公众号服务器URL时验证
    """
    settings = get_settings()
    token = settings.WECHAT_TOKEN

    if not token:
        raise HTTPException(status_code=500, detail="微信Token未配置")

    if verify_signature(token, signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    else:
        raise HTTPException(status_code=403, detail="签名验证失败")


@wechat_router.post("/callback")
async def wechat_callback(request: Request):
    """
    接收微信消息推送

    处理用户发送的消息，返回商品信息或搜索结果
    """
    settings = get_settings()

    # 验证签名（生产环境建议开启）
    # signature = request.query_params.get("signature")
    # timestamp = request.query_params.get("timestamp")
    # nonce = request.query_params.get("nonce")
    # if not verify_signature(settings.WECHAT_TOKEN, signature, timestamp, nonce):
    #     raise HTTPException(status_code=403, detail="签名验证失败")

    try:
        # 解析XML消息
        xml_data = await request.body()
        message = parse_xml_message(xml_data.decode('utf-8'))

        if not message:
            return build_xml_response(
                to_user=message.get("FromUserName"),
                from_user=message.get("ToUserName"),
                content="消息解析失败"
            )

        # 提取消息信息
        from_user = message.get("FromUserName")  # 用户OpenID
        to_user = message.get("ToUserName")      # 公众号ID
        msg_type = message.get("MsgType")        # 消息类型
        content = message.get("Content", "").strip()  # 消息内容

        log.info(f"收到消息 from={from_user}: {content[:100]}")

        # 检查限流
        is_limited = await price_service.cache.is_rate_limited(from_user)
        if is_limited:
            return build_xml_response(
                to_user=from_user,
                from_user=to_user,
                content="您查询得太频繁了，请稍后再试~"
            )

        # 处理不同类型的消息
        if msg_type == "text":
            response = await handle_text_message(content, from_user)
        elif msg_type == "event":
            response = await handle_event_message(message, from_user)
        else:
            response = MessageBuilder.build_text_message("暂不支持该类型消息")

        # 转换为微信XML格式
        if response.get("type") == "text":
            return build_xml_response(
                to_user=from_user,
                from_user=to_user,
                content=response["content"]
            )
        elif response.get("type") == "news":
            return build_news_xml_response(
                to_user=from_user,
                from_user=to_user,
                articles=response["articles"]
            )

        return build_xml_response(
            to_user=from_user,
            from_user=to_user,
            content="处理失败"
        )

    except Exception as e:
        log.error(f"处理微信消息失败: {e}")
        return build_xml_response(
            to_user=from_user if 'from_user' in locals() else "",
            from_user=to_user if 'to_user' in locals() else "",
            content="系统繁忙，请稍后再试"
        )


import re

# URL 正则表达式
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)

async def handle_text_message(content: str, from_user: str) -> dict:
    """
    处理文本消息

    处理优先级：专属指令（数据库配置）> URL > 口令 > 关键词搜索
    """
    # 1. 检查是否是专属指令（优先级高）
    special_cmd = match_special_command(content)

    if special_cmd:
        # 1.1 尝试从数据库配置获取回复
        try:
            manager = get_keyword_manager()
            reply = manager.build_reply_message(special_cmd)
            if reply:
                # 数据库配置了回复内容，直接返回
                return reply
        except Exception as e:
            log.warning(f"从数据库获取回复失败: {e}")

        # 1.2 如果是system类型或未配置，走原有逻辑
        if special_cmd == "帮助":
            return MessageBuilder.build_help_message()

        if special_cmd == "热门":
            return await handle_hot_keywords_message()

        if special_cmd == "壁纸":
            return await handle_wallpaper_message()

        if special_cmd == "猜谜":
            return await handle_riddle_message(from_user)

        if special_cmd == "流量卡":
            return await handle_traffic_card_message()

    # 处理"答案"命令（查看当前谜题答案）
    if content in ["答案", "回答", "揭晓"]:
        return await handle_riddle_answer(from_user)

    # 2. 提取消息中的URL（优先处理URL）
    urls = URL_PATTERN.findall(content)
    if urls:
        # 有链接，优先处理第一个链接
        return await handle_link_message(urls[0])

    # 3. 检查是否包含口令（如 ￥ABC123￥），只有没有URL时才处理口令
    if KoulingParser.is_kouling(content):
        kouling_url = await extract_and_parse_kouling(content)
        if kouling_url:
            return await handle_link_message(kouling_url)
        else:
            # 口令无法解析，提示用户
            return MessageBuilder.build_text_message(
                "检测到口令，但暂时无法解析\n"
                "请直接发送商品链接查询\n"
                "或发送商品名称进行搜索"
            )

    # 4. 没有URL，判断是否是商品关键词
    if IntentClassifier.is_likely_product_keyword(content):
        return await handle_search_message(content)
    else:
        # 不像是商品搜索，返回引导语
        return MessageBuilder.build_text_message(
            IntentClassifier.get_fallback_response(content)
        )


async def handle_link_message(link: str) -> dict:
    """
    处理商品链接

    解析链接 -> 查询商品信息 -> 返回结果
    """
    try:
        # 解析链接
        platform, item_id, extra = await link_parser.parse(link)

        if not platform or not item_id:
            # 检查是否是淘宝/京东链接（暂不支持）
            link_lower = link.lower()
            if "taobao.com" in link_lower or "tmall.com" in link_lower or "tb.cn" in link_lower:
                return MessageBuilder.build_text_message(
                    "🍑 淘宝链接暂时不支持直接查券\n\n"
                    "你可以：\n"
                    "1️⃣ 发送商品名称（如：iPhone 15）让我帮你搜拼多多\n"
                    "2️⃣ 直接发送拼多多商品链接\n\n"
                    "回复【热门】看看拼多多有什么优惠~"
                )
            elif "jd.com" in link_lower or "jingxi.com" in link_lower or "3.cn" in link_lower:
                return MessageBuilder.build_text_message(
                    "🐕 京东链接暂时不支持直接查券\n\n"
                    "你可以：\n"
                    "1️⃣ 发送商品名称（如：洗衣液）让我帮你搜拼多多\n"
                    "2️⃣ 直接发送拼多多商品链接\n\n"
                    "回复【热门】看看拼多多有什么优惠~"
                )
            return MessageBuilder.build_text_message(
                "无法识别该链接，请发送拼多多商品链接或商品名称"
            )

        # 查询商品信息，传递 extra 参数（包含拼多多的 goods_sign）
        product = await price_service.get_product(platform, item_id, extra=extra)

        # 构建回复消息（带人设文案）
        return MessageBuilder.build_product_message_with_persona(product)

    except ProductNotFoundError:
        return MessageBuilder.build_text_message(
            "😔 这款宝贝商家今天没放内部券呢\n\n"
            "没帮您省到钱，小芸送您一个脑筋急转弯开心一下吧！\n"
            "回复【猜谜】马上开始~\n\n"
            "或者点击右上角关注我的日常推文，每天都有新福利哦！"
        )
    except APIError as e:
        log.error(f"查询商品失败: {e}")
        return MessageBuilder.build_text_message(
            "😔 查询失败了呢\n\n"
            "可能网络有点问题，稍后再试一次吧~\n"
            "或者回复【猜谜】先玩个游戏放松一下！"
        )
    except Exception as e:
        log.error(f"处理链接失败: {e}")
        return MessageBuilder.build_text_message(
            "处理失败，请检查链接是否正确\n\n"
            "也可以发送商品名称让我帮你搜索哦~"
        )


async def handle_hot_keywords_message() -> dict:
    """
    处理今日热门关键词查询
    """
    try:
        hot_keywords = await price_service.cache.get_hot_keywords(n=10)
        log.info(f"获取热门关键词结果: {hot_keywords}")
        return MessageBuilder.build_hot_keywords_message(hot_keywords)
    except Exception as e:
        log.error(f"获取热门关键词失败: {e}")
        return MessageBuilder.build_text_message("获取热门关键词失败，请稍后重试")


async def handle_wallpaper_message() -> dict:
    """处理壁纸请求"""
    wallpaper = get_random_wallpaper()
    if wallpaper:
        return MessageBuilder.build_wallpaper_message(wallpaper)
    return MessageBuilder.build_text_message(
        "🎨 壁纸库更新中...\n\n先试试其他功能吧！\n发送【热门】看看今天大家都在买什么~"
    )


async def handle_riddle_message(openid: str) -> dict:
    """处理猜谜请求"""
    try:
        game_manager = get_riddle_game_manager()
        riddle = game_manager.get_random_for_user(openid)
        if riddle:
            return MessageBuilder.build_riddle_message(riddle)
    except Exception as e:
        log.error(f"获取谜语失败: {e}")

    return MessageBuilder.build_text_message(
        "🎯 题库更新中...\n\n先试试其他功能吧！\n发送【热门】看看今天大家都在买什么~"
    )


async def handle_riddle_answer(openid: str) -> dict:
    """处理查看猜谜答案"""
    try:
        game_manager = get_riddle_game_manager()
        riddle = game_manager.get_user_riddle(openid)
        if riddle:
            return MessageBuilder.build_riddle_answer_message(riddle)
    except Exception as e:
        log.error(f"获取用户谜题失败: {e}")

    return MessageBuilder.build_text_message(
        "🤔 你还没有开始猜谜呢！\n\n"
        "回复【猜谜】开始答题\n"
        "回复【热门】查看优惠商品"
    )


async def handle_traffic_card_message() -> dict:
    """处理流量卡推广"""
    if not TRAFFIC_CARD_CONFIG["enabled"]:
        return MessageBuilder.build_text_message(
            "📱 超值流量卡推广暂未启用\n\n"
            "正在和运营商对接中，敬请期待~\n"
            "回复【热门】看看现在有什么优惠商品"
        )
    return MessageBuilder.build_traffic_card_message(TRAFFIC_CARD_CONFIG)


async def handle_search_message(keyword: str) -> dict:
    """
    处理关键词搜索

    返回文本+多条链接，让用户货比三家
    """
    try:
        # 搜索商品（多平台）
        results = await price_service.search(keyword, platform=None, page_size=3)

        if not results:
            # 未找到商品，返回兜底话术+互动诱饵
            return MessageBuilder.build_text_message(
                f"😔 抱歉，关于【{keyword}】暂时没找到合适的优惠商品\n\n"
                f"没帮您省到钱，小芸送您一个脑筋急转弯开心一下吧！\n"
                f"回复【猜谜】马上开始~\n\n"
                f"或者回复【热门】看看今天大家都在买什么！"
            )

        # 合并所有平台的商品
        all_products = []
        for result in results:
            all_products.extend(result.products)

        if not all_products:
            return MessageBuilder.build_text_message(
                f"😔 关于【{keyword}】暂时没找到相关商品\n\n"
                f"试试换个关键词？比如：\n"
                f"• 具体型号（如：iPhone 15）\n"
                f"• 品类+用途（如：儿童护眼台灯）\n\n"
                f"回复【猜谜】先玩个游戏放松一下！"
            )

        # 取前3个商品，按价格排序
        top_products = sorted(all_products, key=lambda x: x.final_price)[:3]

        # 返回文本+链接格式（让用户货比三家）
        result = MessageBuilder.build_search_comparison_message(keyword, top_products)
        # log.info(f"搜索返回内容类型: {result.get('type')}")
        # log.info(f"搜索返回内容预览: {result.get('content', '')[:150]}...")
        return result

    except Exception as e:
        log.error(f"搜索失败: {e}")
        return MessageBuilder.build_text_message(
            "😔 搜索时遇到了一点小麻烦\n\n"
            "稍后再试一次，或者回复【猜谜】先玩个游戏~"
        )


async def handle_event_message(message: dict, from_user: str) -> dict:
    """
    处理事件消息（关注、取消关注、菜单点击等）
    """
    event = message.get("Event")

    if event == "subscribe":
        # 关注事件
        return MessageBuilder.build_text_message(
            "感谢关注小芸生活助手！🎉\n\n"
            "发送商品链接，自动查询优惠券\n"
            "发送关键词，搜索全网低价\n\n"
            "回复「帮助」查看使用指南"
        )
    elif event == "unsubscribe":
        # 取消关注
        log.info(f"用户取消关注: {message.get('FromUserName')}")
        return MessageBuilder.build_text_message("")
    elif event == "CLICK":
        # 菜单点击事件
        event_key = message.get("EventKey", "")
        log.info(f"用户点击菜单: {event_key}")

        # 将菜单事件转换为对应的指令处理
        command = handle_menu_event(event_key)
        if command:
            # 复用文本消息处理逻辑
            return await handle_text_message(command, from_user)
        else:
            return MessageBuilder.build_text_message("该功能暂未配置，试试其他菜单吧~")
    elif event == "VIEW":
        # 菜单链接跳转事件（不需要处理，微信自动跳转）
        log.info(f"用户点击链接菜单: {message.get('EventKey')}")
        return MessageBuilder.build_text_message("")

    return MessageBuilder.build_text_message("")


def parse_xml_message(xml_data: str) -> Optional[dict]:
    """
    解析微信XML消息

    简单实现，生产环境建议使用xmltodict库
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_data)

        message = {}
        for child in root:
            message[child.tag] = child.text

        return message
    except Exception as e:
        log.error(f"解析XML失败: {e}")
        return None


def build_xml_response(to_user: str, from_user: str, content: str) -> str:
    """
    构建文本消息XML
    """
    import time

    xml_template = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

    return PlainTextResponse(xml_template, media_type="application/xml")


def build_news_xml_response(to_user: str, from_user: str, articles: list) -> str:
    """
    构建图文消息XML
    """
    import time

    items_xml = ""
    for i, article in enumerate(articles):
        items_xml += f"""<item>
<Title><![CDATA[{article['title']}]]></Title>
<Description><![CDATA[{article['description']}]]></Description>
<PicUrl><![CDATA[{article['pic_url']}]]></PicUrl>
<Url><![CDATA[{article['url']}]]></Url>
</item>"""

    xml_template = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[news]]></MsgType>
<ArticleCount>{len(articles)}</ArticleCount>
<Articles>{items_xml}</Articles>
</xml>"""

    return PlainTextResponse(xml_template, media_type="application/xml")
