"""
统一数据库管理模块
提供共享的数据库连接和初始化管理
"""
import os
import sqlite3
from typing import Optional
from pathlib import Path

# 尝试使用 loguru，如果不存在则使用标准库 logging
try:
    from core.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class Database:
    """统一数据库管理类（单例模式）"""

    _instance: Optional['Database'] = None
    _db_path: str = "data/app.db"

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return

        if db_path:
            self._db_path = db_path

        # 确保目录存在
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)

        self._initialized = True
        logger.info(f"数据库初始化: {self._db_path}")

    @property
    def db_path(self) -> str:
        return self._db_path

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return cursor.fetchone() is not None

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """检查表中列是否存在"""
        with self.get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns

    def close(self):
        """关闭数据库（主要用于测试）"""
        pass  # 使用 with 语句自动管理连接

    @classmethod
    def reset_instance(cls):
        """重置单例（主要用于测试）"""
        cls._instance = None


def get_db() -> Database:
    """获取数据库实例"""
    return Database()
