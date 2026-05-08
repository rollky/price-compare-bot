"""
猜谜题库模型
用于存储和管理脑筋急转弯题目
"""
import json
import random
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

# 尝试使用 loguru，如果不存在则使用标准库 logging
try:
    from core.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
from models.database import get_db


@dataclass
class RiddleItem:
    """猜谜题目"""
    id: Optional[int] = None
    question: str = ""           # 问题
    answer: str = ""             # 答案
    hint: str = ""               # 提示
    category: str = ""           # 分类（如：趣味、益智、儿童）
    difficulty: int = 1          # 难度：1-简单，2-中等，3-困难
    is_active: bool = True       # 是否启用
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()


class RiddleManager:
    """猜谜管理器"""

    _initialized = False

    def __init__(self):
        self._db = get_db()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        # 创建表
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS riddles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                hint TEXT,
                category TEXT DEFAULT 'general',
                difficulty INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # 只初始化一次默认数据
        if not RiddleManager._initialized:
            self._init_default_data()
            RiddleManager._initialized = True

    def _init_default_data(self):
        """初始化默认谜语数据"""
        default_riddles = [
            # 经典谜语
            {
                "question": "🏮 什么东西越洗越脏？",
                "answer": "水",
                "hint": "想想每天用的...",
                "category": "经典",
                "difficulty": 1
            },
            {
                "question": "🏮 什么东西有头无脚？",
                "answer": "硬币",
                "hint": "买东西会用到...",
                "category": "经典",
                "difficulty": 1
            },
            {
                "question": "🏮 什么东西打破了才能吃？",
                "answer": "鸡蛋",
                "hint": "早餐常见...",
                "category": "经典",
                "difficulty": 1
            },
            {
                "question": "🏮 什么东西越生气越大？",
                "answer": "脾气",
                "hint": "情绪相关...",
                "category": "经典",
                "difficulty": 1
            },
            {
                "question": "🏮 什么东西属于你，但别人用的比你多？",
                "answer": "名字",
                "hint": "每个人都有...",
                "category": "经典",
                "difficulty": 1
            },
            # 趣味谜语
            {
                "question": "🎯 什么动物最怕冷？",
                "answer": "企鹅",
                "hint": "它生活在南极...",
                "category": "趣味",
                "difficulty": 2
            },
            {
                "question": "🎯 什么东西有面没有口，有脚没有手？",
                "answer": "桌子",
                "hint": "家具的一种...",
                "category": "趣味",
                "difficulty": 1
            },
            {
                "question": "🎯 什么门永远关不上？",
                "answer": "球门",
                "hint": "运动场上常见...",
                "category": "趣味",
                "difficulty": 1
            },
            {
                "question": "🎯 什么海没有水？",
                "answer": "辞海",
                "hint": "一本书的名字...",
                "category": "趣味",
                "difficulty": 2
            },
            {
                "question": "🎯 什么车没有人能开？",
                "answer": "风车",
                "hint": "靠风转动的...",
                "category": "趣味",
                "difficulty": 1
            },
            # 益智谜语
            {
                "question": "🧩 什么东西有五个头，但人不觉得它怪？",
                "answer": "手",
                "hint": "每个人都有两只...",
                "category": "益智",
                "difficulty": 2
            },
            {
                "question": "🧩 什么东西从这边看由远变近，从那边看由近变远？",
                "answer": "路",
                "hint": "我们每天都在走...",
                "category": "益智",
                "difficulty": 3
            },
            {
                "question": "🧩 什么东西早上四条腿，中午两条腿，晚上三条腿？",
                "answer": "人",
                "hint": "一生的不同阶段...",
                "category": "益智",
                "difficulty": 2
            },
            {
                "question": "🧩 什么东西有眼睛却看不见？",
                "answer": "针",
                "hint": "缝衣服用的...",
                "category": "益智",
                "difficulty": 2
            },
            {
                "question": "🧩 什么东西越热越爱出来？",
                "answer": "汗",
                "hint": "夏天常有...",
                "category": "益智",
                "difficulty": 1
            },
            # 儿童谜语
            {
                "question": "🎈 红红果子棍上挂，外裹糖儿味道佳？",
                "answer": "冰糖葫芦",
                "hint": "冬天街头常见...",
                "category": "儿童",
                "difficulty": 1
            },
            {
                "question": "🎈 耳朵长，尾巴短，只吃菜，不吃饭？",
                "answer": "兔子",
                "hint": "蹦蹦跳跳的小动物...",
                "category": "儿童",
                "difficulty": 1
            },
            {
                "question": "🎈 身穿绿衣裳，肚里水汪汪，生的子儿多，个个黑脸膛？",
                "answer": "西瓜",
                "hint": "夏天解暑水果...",
                "category": "儿童",
                "difficulty": 1
            },
            {
                "question": "🎈 五个兄弟，住在一起，名字不同，高矮不齐？",
                "answer": "手指",
                "hint": "伸出手看看...",
                "category": "儿童",
                "difficulty": 1
            },
            {
                "question": "🎈 屋子方方，有门没窗，屋外热烘，屋里冰霜？",
                "answer": "冰箱",
                "hint": "保存食物用的...",
                "category": "儿童",
                "difficulty": 1
            },
            # 生活谜语
            {
                "question": "🏠 什么东西每天都要开口，但从来不说话？",
                "answer": "门",
                "hint": "进出房间的...",
                "category": "生活",
                "difficulty": 1
            },
            {
                "question": "🏠 什么东西有脚却从不走路？",
                "answer": "床",
                "hint": "睡觉用的...",
                "category": "生活",
                "difficulty": 1
            },
            {
                "question": "🏠 什么东西越擦越小？",
                "answer": "肥皂",
                "hint": "洗澡洗手用的...",
                "category": "生活",
                "difficulty": 1
            },
            {
                "question": "🏠 什么东西有风就不动，没风就动？",
                "answer": "扇子",
                "hint": "夏天用来纳凉...",
                "category": "生活",
                "difficulty": 2
            },
            {
                "question": "🏠 什么东西有嘴却不能喝？",
                "answer": "茶壶嘴",
                "hint": "泡茶用的器具...",
                "category": "生活",
                "difficulty": 2
            },
        ]

        # 检查是否已有数据
        existing = self.get_all(include_inactive=True)
        if len(existing) < len(default_riddles):
            for riddle in default_riddles:
                # 检查是否已存在相同问题
                if not self._exists_by_question(riddle["question"]):
                    self.create(
                        question=riddle["question"],
                        answer=riddle["answer"],
                        hint=riddle.get("hint", ""),
                        category=riddle.get("category", "general"),
                        difficulty=riddle.get("difficulty", 1)
                    )
            logger.info(f"初始化默认谜语数据完成，共 {len(default_riddles)} 条")

    def _exists_by_question(self, question: str) -> bool:
        """检查是否已存在相同问题"""
        with self._db.get_connection() as conn:
            cursor = conn.execute('SELECT id FROM riddles WHERE question = ?', (question,))
            row = cursor.fetchone()

        return row is not None

    def create(self, question: str, answer: str, hint: str = "",
               category: str = "general", difficulty: int = 1) -> RiddleItem:
        """创建谜语"""
        now = datetime.now().isoformat()

        cursor = self._db.execute('''
            INSERT INTO riddles (question, answer, hint, category, difficulty, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (question, answer, hint, category, difficulty, 1, now, now))

        item_id = cursor.lastrowid
        logger.info(f"创建谜语: {question[:20]}...")
        return self.get_by_id(item_id)

    def get_by_id(self, item_id: int) -> Optional[RiddleItem]:
        """根据ID获取"""
        with self._db.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM riddles WHERE id = ?', (item_id,))
            row = cursor.fetchone()

        if row:
            return self._row_to_item(row)
        return None

    def get_all(self, category: Optional[str] = None,
                difficulty: Optional[int] = None,
                include_inactive: bool = False) -> List[RiddleItem]:
        """获取所有谜语"""
        with self._db.get_connection() as conn:
            query = 'SELECT * FROM riddles WHERE 1=1'
            params = []

            if not include_inactive:
                query += ' AND is_active = 1'

            if category:
                query += ' AND category = ?'
                params.append(category)

            if difficulty:
                query += ' AND difficulty = ?'
                params.append(difficulty)

            query += ' ORDER BY id ASC'

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_item(row) for row in rows]

    def get_random(self, category: Optional[str] = None,
                   difficulty: Optional[int] = None) -> Optional[RiddleItem]:
        """随机获取一个谜语"""
        items = self.get_all(category=category, difficulty=difficulty)
        if items:
            return random.choice(items)
        return None

    def update(self, item_id: int, **kwargs) -> Optional[RiddleItem]:
        """更新谜语"""
        allowed_fields = ['question', 'answer', 'hint', 'category', 'difficulty', 'is_active']
        updates = []
        values = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key == 'is_active':
                    values.append(1 if value else 0)
                else:
                    values.append(value)

        if not updates:
            return self.get_by_id(item_id)

        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(item_id)

        self._db.execute(f'''
            UPDATE riddles SET {', '.join(updates)} WHERE id = ?
        ''', values)

        logger.info(f"更新谜语 ID={item_id}")
        return self.get_by_id(item_id)

    def delete(self, item_id: int) -> bool:
        """删除谜语"""
        cursor = self._db.execute('DELETE FROM riddles WHERE id = ?', (item_id,))
        affected = cursor.rowcount

        if affected > 0:
            logger.info(f"删除谜语 ID={item_id}")
        return affected > 0

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        with self._db.get_connection() as conn:
            cursor = conn.execute('SELECT DISTINCT category FROM riddles WHERE is_active = 1')
            rows = cursor.fetchall()

        return [row[0] for row in rows]

    def count(self, category: Optional[str] = None) -> int:
        """获取谜语数量"""
        with self._db.get_connection() as conn:
            query = 'SELECT COUNT(*) FROM riddles WHERE is_active = 1'
            params = []

            if category:
                query += ' AND category = ?'
                params.append(category)

            cursor = conn.execute(query, params)
            count = cursor.fetchone()[0]

        return count

    def _row_to_item(self, row) -> RiddleItem:
        """数据库行转对象"""
        return RiddleItem(
            id=row[0],
            question=row[1],
            answer=row[2],
            hint=row[3] if row[3] else "",
            category=row[4] if row[4] else "general",
            difficulty=row[5] if row[5] else 1,
            is_active=bool(row[6]) if row[6] else True,
            created_at=row[7],
            updated_at=row[8]
        )


# 用户猜谜状态管理（简单实现，生产环境建议用Redis）
class RiddleGameManager:
    """猜谜游戏状态管理器"""

    def __init__(self):
        self._user_riddles = {}  # {openid: riddle_id}
        self._riddle_manager = None

    def _get_manager(self) -> RiddleManager:
        if self._riddle_manager is None:
            self._riddle_manager = RiddleManager()
        return self._riddle_manager

    def set_user_riddle(self, openid: str, riddle_id: int):
        """记录用户当前的谜题ID"""
        self._user_riddles[openid] = riddle_id

    def get_user_riddle(self, openid: str) -> Optional[RiddleItem]:
        """获取用户当前的谜题"""
        riddle_id = self._user_riddles.get(openid)
        if riddle_id:
            return self._get_manager().get_by_id(riddle_id)
        return None

    def clear_user_riddle(self, openid: str):
        """清除用户的谜题记录"""
        if openid in self._user_riddles:
            del self._user_riddles[openid]

    def get_random_for_user(self, openid: str) -> Optional[RiddleItem]:
        """为用户获取一个新的随机谜题（尽量不重复）"""
        # 获取所有可用谜题
        all_riddles = self._get_manager().get_all()
        if not all_riddles:
            return None

        # 如果只有一个，直接返回
        if len(all_riddles) == 1:
            riddle = all_riddles[0]
            self.set_user_riddle(openid, riddle.id)
            return riddle

        # 获取用户上次的谜题
        last_riddle = self.get_user_riddle(openid)
        last_id = last_riddle.id if last_riddle else None

        # 随机选择一个不同于上次的
        import random
        available = [r for r in all_riddles if r.id != last_id]
        if available:
            riddle = random.choice(available)
        else:
            riddle = random.choice(all_riddles)

        self.set_user_riddle(openid, riddle.id)
        return riddle


# 全局实例
_riddle_manager: Optional[RiddleManager] = None
_riddle_game_manager: Optional[RiddleGameManager] = None


def get_riddle_manager() -> RiddleManager:
    """获取谜语管理器单例"""
    global _riddle_manager
    if _riddle_manager is None:
        _riddle_manager = RiddleManager()
    return _riddle_manager


def get_riddle_game_manager() -> RiddleGameManager:
    """获取猜谜游戏管理器单例"""
    global _riddle_game_manager
    if _riddle_game_manager is None:
        _riddle_game_manager = RiddleGameManager()
    return _riddle_game_manager
