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
            response = await handle_event_message(message)
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

    处理优先级：URL > 口令 > 关键词搜索
    """
    # 1. 检查是否是命令
    if content in ["帮助", "help", "菜单", "menu"]:
        return MessageBuilder.build_help_message()

    # 2. 提取消息中的URL（优先处理URL）
    urls = URL_PATTERN.findall(content)
    if urls:
        # 有链接，优先处理第一个链接
        log.info(f"从消息中提取到链接: {urls[0]}")
        return await handle_link_message(urls[0])

    # 3. 检查是否包含口令（如 ￥ABC123￥），只有没有URL时才处理口令
    if KoulingParser.is_kouling(content):
        log.info(f"检测到口令: {content[:50]}")
        kouling_url = await extract_and_parse_kouling(content)
        if kouling_url:
            log.info(f"口令解析成功: {kouling_url}")
            return await handle_link_message(kouling_url)
        else:
            # 口令无法解析，提示用户
            return MessageBuilder.build_text_message(
                "检测到口令，但暂时无法解析\n"
                "请直接发送商品链接查询\n"
                "或发送商品名称进行搜索"
            )

    # 4. 没有URL，作为关键词搜索
    return await handle_search_message(content)


async def handle_link_message(link: str) -> dict:
    """
    处理商品链接

    解析链接 -> 查询商品信息 -> 返回结果
    """
    try:
        # 解析链接
        platform, item_id, extra = await link_parser.parse(link)

        if not platform or not item_id:
            return MessageBuilder.build_text_message(
                "无法识别该链接，请发送淘宝、京东或拼多多的商品链接"
            )

        # 查询商品信息，传递 extra 参数（包含拼多多的 goods_sign）
        product = await price_service.get_product(platform, item_id, extra=extra)

        # 构建回复消息
        return MessageBuilder.build_product_message(product)

    except ProductNotFoundError:
        return MessageBuilder.build_text_message("该商品已下架或不存在")
    except APIError as e:
        log.error(f"查询商品失败: {e}")
        return MessageBuilder.build_text_message("查询商品信息失败，请稍后重试")
    except Exception as e:
        log.error(f"处理链接失败: {e}")
        return MessageBuilder.build_text_message("处理失败，请检查链接是否正确")


async def handle_search_message(keyword: str) -> dict:
    """
    处理关键词搜索

    在多个平台搜索商品并返回结果
    """
    try:
        # 搜索商品（多平台）
        results = await price_service.search(keyword, platform=None, page_size=3)

        if not results:
            return MessageBuilder.build_text_message(f'未找到 "{keyword}" 的相关商品')

        # 合并所有平台的商品
        all_products = []
        for result in results:
            all_products.extend(result.products)

        if not all_products:
            return MessageBuilder.build_text_message(f'未找到 "{keyword}" 的相关商品')

        # 取前3个商品构建多图文消息（当前仅支持拼多多）
        # 恢复多平台时改为: 每个平台取第一个
        all_products = []
        for result in results:
            all_products.extend(result.products)

        # 取前3个
        top_products = all_products[:3]

        if len(top_products) == 1:
            return MessageBuilder.build_product_message(top_products[0])
        else:
            # 构建多图文消息（3个拼多多商品）
            return MessageBuilder.build_multi_platform_message(top_products)

    except Exception as e:
        log.error(f"搜索失败: {e}")
        return MessageBuilder.build_text_message("搜索失败，请稍后重试")


async def handle_event_message(message: dict) -> dict:
    """
    处理事件消息（关注、取消关注等）
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

    return PlainTextResponse(xml_template)


def build_news_xml_response(to_user: str, from_user: str, articles: list) -> str:
    """
    构建图文消息XML
    """
    import time

    items_xml = ""
    for article in articles:
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

    return PlainTextResponse(xml_template)
