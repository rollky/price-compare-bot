"""
日志配置
"""
import sys
from loguru import logger
from typing import Any


def setup_logger(level: str = "INFO") -> Any:
    """配置日志"""
    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )

    # 添加文件日志
    logger.add(
        "logs/app.log",
        level=level,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    )

    # 错误日志单独文件
    logger.add(
        "logs/error.log",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    return logger


# 全局logger实例
logger = setup_logger()
