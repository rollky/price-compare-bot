"""
微信公众号菜单管理
创建、查询、删除自定义菜单
"""
import json
import requests
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

from config import get_settings
from core.logger import logger


@dataclass
class MenuButton:
    """菜单按钮"""
    name: str
    type: Optional[str] = None  # click, view, miniprogram, scancode_push等
    key: Optional[str] = None   # click类型需要
    url: Optional[str] = None   # view类型需要
    sub_buttons: Optional[List['MenuButton']] = None  # 子菜单

    def to_dict(self) -> dict:
        """转为微信接口格式"""
        result = {"name": self.name}

        if self.sub_buttons:
            # 有子菜单
            result["sub_button"] = [btn.to_dict() for btn in self.sub_buttons]
        else:
            # 无子菜单
            if self.type:
                result["type"] = self.type
            if self.key:
                result["key"] = self.key
            if self.url:
                result["url"] = self.url

        return result


class WechatMenuManager:
    """微信菜单管理器"""

    BASE_URL = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self):
        self.settings = get_settings()
        self.appid = self.settings.WECHAT_APPID
        self.appsecret = self.settings.WECHAT_APPSECRET
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> Optional[str]:
        """获取access_token"""
        if self._access_token:
            return self._access_token

        if not self.appid or not self.appsecret:
            logger.error("微信AppID或AppSecret未配置")
            return None

        url = f"{self.BASE_URL}/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "access_token" in data:
                self._access_token = data["access_token"]
                logger.info("获取微信access_token成功")
                return self._access_token
            else:
                logger.error(f"获取access_token失败: {data}")
                return None
        except Exception as e:
            logger.error(f"获取access_token异常: {e}")
            return None

    def create_menu(self, buttons: List[MenuButton]) -> bool:
        """
        创建自定义菜单

        Args:
            buttons: 菜单按钮列表（最多3个一级菜单）

        Returns:
            是否创建成功
        """
        access_token = self._get_access_token()
        if not access_token:
            return False

        url = f"{self.BASE_URL}/menu/create"
        params = {"access_token": access_token}

        # 构建菜单数据
        menu_data = {
            "button": [btn.to_dict() for btn in buttons]
        }

        try:
            response = requests.post(
                url,
                params=params,
                json=menu_data,
                timeout=10
            )
            result = response.json()

            if result.get("errcode") == 0:
                logger.info("创建菜单成功")
                return True
            else:
                logger.error(f"创建菜单失败: {result}")
                return False
        except Exception as e:
            logger.error(f"创建菜单异常: {e}")
            return False

    def get_menu(self) -> Optional[dict]:
        """
        查询当前菜单

        Returns:
            菜单配置或None
        """
        access_token = self._get_access_token()
        if not access_token:
            return None

        url = f"{self.BASE_URL}/menu/get"
        params = {"access_token": access_token}

        try:
            response = requests.get(url, params=params, timeout=10)
            result = response.json()

            if "menu" in result:
                return result["menu"]
            else:
                logger.warning(f"获取菜单失败或无菜单: {result}")
                return None
        except Exception as e:
            logger.error(f"获取菜单异常: {e}")
            return None

    def delete_menu(self) -> bool:
        """
        删除所有菜单

        Returns:
            是否删除成功
        """
        access_token = self._get_access_token()
        if not access_token:
            return False

        url = f"{self.BASE_URL}/menu/delete"
        params = {"access_token": access_token}

        try:
            response = requests.get(url, params=params, timeout=10)
            result = response.json()

            if result.get("errcode") == 0:
                logger.info("删除菜单成功")
                return True
            else:
                logger.error(f"删除菜单失败: {result}")
                return False
        except Exception as e:
            logger.error(f"删除菜单异常: {e}")
            return False

    def create_default_menu(self) -> bool:
        """创建默认菜单配置"""
        buttons = [
            MenuButton(
                name="查优惠券",
                sub_buttons=[
                    MenuButton(
                        name="今日热门",
                        type="click",
                        key="MENU_HOT"
                    ),
                    MenuButton(
                        name="使用帮助",
                        type="click",
                        key="MENU_HELP"
                    ),
                    MenuButton(
                        name="猜谜游戏",
                        type="click",
                        key="MENU_RIDDLE"
                    )
                ]
            ),
            MenuButton(
                name="领福利",
                type="click",
                key="MENU_WALLPAPER"
            ),
            MenuButton(
                name="流量卡",
                type="view",
                url="https://ka.huojukj.com/?u=112233"
            )
        ]

        return self.create_menu(buttons)


# 菜单事件处理映射
MENU_EVENT_HANDLERS = {
    "MENU_HOT": "热门",
    "MENU_HELP": "帮助",
    "MENU_RIDDLE": "猜谜",
    "MENU_WALLPAPER": "壁纸",
}


def handle_menu_event(event_key: str) -> Optional[str]:
    """
    处理菜单点击事件

    Args:
        event_key: 菜单key

    Returns:
        对应的指令类型或None
    """
    return MENU_EVENT_HANDLERS.get(event_key)


# 全局实例
_menu_manager: Optional[WechatMenuManager] = None


def get_menu_manager() -> WechatMenuManager:
    """获取菜单管理器单例"""
    global _menu_manager
    if _menu_manager is None:
        _menu_manager = WechatMenuManager()
    return _menu_manager
