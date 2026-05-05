"""
关键词管理模型
用于存储和管理专属指令关键词
"""
import json
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

from core.logger import logger


@dataclass
class KeywordItem:
    """关键词项"""
    id: Optional[int] = None
    command_type: str = ""  # 指令类型，如"壁纸"、"猜谜"
    keywords: List[str] = None  # 关键词列表
    description: str = ""  # 描述
    priority: int = 0  # 优先级，数字越大越优先
    is_active: bool = True  # 是否启用
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()


class KeywordManager:
    """关键词管理器"""

    def __init__(self, db_path: str = "data/keywords.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        import os

        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_type TEXT NOT NULL UNIQUE,
                keywords TEXT NOT NULL,  -- JSON格式存储列表
                description TEXT,
                priority INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

        # 初始化默认数据
        self._init_default_data()

    def _init_default_data(self):
        """初始化默认关键词数据"""
        default_keywords = {
            "壁纸": {
                "keywords": ["壁纸", "wallpaper", "背景图", "手机壁纸"],
                "description": "获取精美手机壁纸",
                "priority": 10
            },
            "猜谜": {
                "keywords": ["猜谜", "脑筋急转弯", "谜语", "答题", "riddle"],
                "description": "趣味猜谜游戏",
                "priority": 10
            },
            "流量卡": {
                "keywords": ["流量卡", "流量", "手机卡", "电话卡", "大流量"],
                "description": "超值流量卡推广",
                "priority": 5
            },
            "热门": {
                "keywords": ["热门", "今日热门", "hot", "排行榜"],
                "description": "查看今日热门搜索",
                "priority": 10
            },
            "帮助": {
                "keywords": ["帮助", "help", "菜单", "menu", "怎么用"],
                "description": "查看使用帮助",
                "priority": 20
            },
        }

        for cmd_type, data in default_keywords.items():
            if not self.get_by_type(cmd_type):
                self.create(
                    command_type=cmd_type,
                    keywords=data["keywords"],
                    description=data["description"],
                    priority=data["priority"]
                )

    def create(self, command_type: str, keywords: List[str],
               description: str = "", priority: int = 0) -> KeywordItem:
        """创建关键词"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO keywords (command_type, keywords, description, priority, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (command_type, json.dumps(keywords, ensure_ascii=False),
              description, priority, 1, now, now))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"创建关键词: {command_type}")
        return self.get_by_id(item_id)

    def get_by_id(self, item_id: int) -> Optional[KeywordItem]:
        """根据ID获取"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM keywords WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_item(row)
        return None

    def get_by_type(self, command_type: str) -> Optional[KeywordItem]:
        """根据类型获取"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM keywords WHERE command_type = ?', (command_type,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_item(row)
        return None

    def get_all(self, include_inactive: bool = False) -> List[KeywordItem]:
        """获取所有关键词"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if include_inactive:
            cursor.execute('SELECT * FROM keywords ORDER BY priority DESC, id ASC')
        else:
            cursor.execute('SELECT * FROM keywords WHERE is_active = 1 ORDER BY priority DESC, id ASC')

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_item(row) for row in rows]

    def update(self, item_id: int, **kwargs) -> Optional[KeywordItem]:
        """更新关键词"""
        import sqlite3

        allowed_fields = ['command_type', 'keywords', 'description', 'priority', 'is_active']
        updates = []
        values = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key == 'keywords':
                    values.append(json.dumps(value, ensure_ascii=False))
                elif key == 'is_active':
                    values.append(1 if value else 0)
                else:
                    values.append(value)

        if not updates:
            return self.get_by_id(item_id)

        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(item_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(f'''
            UPDATE keywords SET {', '.join(updates)} WHERE id = ?
        ''', values)

        conn.commit()
        conn.close()

        logger.info(f"更新关键词 ID={item_id}")
        return self.get_by_id(item_id)

    def delete(self, item_id: int) -> bool:
        """删除关键词"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM keywords WHERE id = ?', (item_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            logger.info(f"删除关键词 ID={item_id}")
        return affected > 0

    def get_keywords_dict(self) -> Dict[str, List[str]]:
        """获取关键词字典格式（兼容原有代码）"""
        items = self.get_all(include_inactive=False)
        result = {}
        for item in items:
            result[item.command_type] = item.keywords
        return result

    def match_command(self, text: str) -> Optional[str]:
        """
        匹配指令
        返回指令类型或None
        """
        text_lower = text.lower().strip()
        items = self.get_all(include_inactive=False)

        # 按优先级排序，高优先级先匹配
        items.sort(key=lambda x: x.priority, reverse=True)

        for item in items:
            for keyword in item.keywords:
                if text_lower == keyword.lower():
                    return item.command_type
        return None

    def _row_to_item(self, row) -> KeywordItem:
        """数据库行转对象"""
        return KeywordItem(
            id=row[0],
            command_type=row[1],
            keywords=json.loads(row[2]),
            description=row[3],
            priority=row[4],
            is_active=bool(row[5]),
            created_at=row[6],
            updated_at=row[7]
        )


# 全局实例
_keyword_manager: Optional[KeywordManager] = None


def get_keyword_manager() -> KeywordManager:
    """获取关键词管理器单例"""
    global _keyword_manager
    if _keyword_manager is None:
        _keyword_manager = KeywordManager()
    return _keyword_manager
