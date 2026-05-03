"""
每日热门商品推送脚本
定时搜索热门商品并发送模板消息
"""
import asyncio
import httpx
from datetime import datetime

from config import get_settings
from services.price_service import PriceService
from services.message_builder import MessageBuilder

# 热门关键词列表
HOT_KEYWORDS = [
    "iPhone 15",
    "洗衣液",
    "零食",
    "纸巾",
    "耳机",
]


async def get_access_token() -> str:
    """获取微信access_token"""
    settings = get_settings()
    appid = settings.WECHAT_APPID
    secret = settings.WECHAT_APPSECRET

    if not appid or not secret:
        raise ValueError("微信AppID或AppSecret未配置")

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        return data.get("access_token")


async def send_template_message(openid: str, template_id: str, data: dict, access_token: str):
    """
    发送模板消息

    Args:
        openid: 用户OpenID
        template_id: 模板ID（需在公众号后台申请）
        data: 模板数据
        access_token: 接口调用凭证
    """
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"

    payload = {
        "touser": openid,
        "template_id": template_id,
        "url": data.get("url", ""),  # 点击跳转链接
        "data": {
            "first": {"value": data.get("title", "今日热门推荐"), "color": "#173177"},
            "keyword1": {"value": data.get("product_name", ""), "color": "#173177"},
            "keyword2": {"value": data.get("price", ""), "color": "#FF0000"},
            "keyword3": {"value": data.get("platform", ""), "color": "#173177"},
            "remark": {"value": data.get("remark", "点击查看详情"), "color": "#173177"},
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        result = response.json()

        if result.get("errcode") != 0:
            print(f"发送失败 {openid}: {result}")
        else:
            print(f"发送成功 {openid}")

        return result


async def search_hot_products():
    """搜索热门商品"""
    price_service = PriceService()
    await price_service.initialize()

    hot_products = []

    for keyword in HOT_KEYWORDS[:3]:  # 只搜前3个关键词
        try:
            results = await price_service.search(keyword, platform=None, page_size=1)
            for result in results:
                if result.products:
                    # 取每个平台第一个结果
                    hot_products.append(result.products[0])
                    break  # 每个关键词只取一个
        except Exception as e:
            print(f"搜索 {keyword} 失败: {e}")

    await price_service.shutdown()
    return hot_products


async def main():
    """主函数：每日推送"""
    print(f"开始执行每日推送任务: {datetime.now()}")

    # 1. 获取access_token
    try:
        access_token = await get_access_token()
        print(f"获取access_token成功")
    except Exception as e:
        print(f"获取access_token失败: {e}")
        return

    # 2. 搜索热门商品
    hot_products = await search_hot_products()
    if not hot_products:
        print("未找到热门商品")
        return

    print(f"找到 {len(hot_products)} 个热门商品")

    # 3. 构建推送内容（取第一个商品作为今日推荐）
    product = hot_products[0]
    push_data = {
        "title": "🎉 今日热门推荐",
        "product_name": product.title[:20] + "..." if len(product.title) > 20 else product.title,
        "price": f"¥{product.final_price}",
        "platform": product.platform.value,
        "url": product.promotion_link or product.product_url,
        "remark": f"优惠券¥{product.coupon.amount}" if product.coupon else "限时优惠，点击抢购",
    }

    # 4. 获取用户列表（需要从数据库读取已关注的用户OpenID）
    # 这里示例写死，实际应该从数据库读取
    user_openids = [
        # "oJh5M6_xXTNc3F7kUTi0FzH_Yieo",  # 示例用户
    ]

    if not user_openids:
        print("没有用户需要推送")
        return

    # 5. 发送模板消息
    template_id = "your_template_id_here"  # 需要在公众号后台申请

    for openid in user_openids:
        try:
            await send_template_message(openid, template_id, push_data, access_token)
        except Exception as e:
            print(f"推送失败 {openid}: {e}")

    print("推送任务完成")


if __name__ == "__main__":
    asyncio.run(main())
