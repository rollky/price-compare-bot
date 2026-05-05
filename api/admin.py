"""
管理后台API
关键词管理、系统配置等
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from models.keyword import KeywordManager, get_keyword_manager, KeywordItem
from core.logger import logger

admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ========== 数据模型 ==========

class KeywordCreate(BaseModel):
    command_type: str
    keywords: List[str]
    description: str = ""
    priority: int = 0
    reply_type: str = "text"  # text/news/system
    reply_content: str = ""


class KeywordUpdate(BaseModel):
    command_type: Optional[str] = None
    keywords: Optional[List[str]] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    reply_type: Optional[str] = None
    reply_content: Optional[str] = None


class KeywordResponse(BaseModel):
    id: int
    command_type: str
    keywords: List[str]
    description: str
    priority: int
    is_active: bool
    reply_type: str
    reply_content: str
    created_at: Optional[str]
    updated_at: Optional[str]


class KeywordListResponse(BaseModel):
    total: int
    items: List[KeywordResponse]


class APIResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


# ========== API接口 ==========

@admin_router.get("/keywords", response_model=KeywordListResponse)
async def get_keywords(
    include_inactive: bool = Query(False, description="是否包含已禁用的")
):
    """获取所有关键词"""
    manager = get_keyword_manager()
    items = manager.get_all(include_inactive=include_inactive)

    return KeywordListResponse(
        total=len(items),
        items=[KeywordResponse(
            id=item.id,
            command_type=item.command_type,
            keywords=item.keywords,
            description=item.description,
            priority=item.priority,
            is_active=item.is_active,
            reply_type=item.reply_type,
            reply_content=item.reply_content,
            created_at=item.created_at,
            updated_at=item.updated_at
        ) for item in items]
    )


@admin_router.get("/keywords/{item_id}", response_model=KeywordResponse)
async def get_keyword(item_id: int):
    """获取单个关键词"""
    manager = get_keyword_manager()
    item = manager.get_by_id(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="关键词不存在")

    return KeywordResponse(
        id=item.id,
        command_type=item.command_type,
        keywords=item.keywords,
        description=item.description,
        priority=item.priority,
        is_active=item.is_active,
        reply_type=item.reply_type,
        reply_content=item.reply_content,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@admin_router.post("/keywords", response_model=APIResponse)
async def create_keyword(data: KeywordCreate):
    """创建关键词"""
    manager = get_keyword_manager()

    # 检查是否已存在
    existing = manager.get_by_type(data.command_type)
    if existing:
        raise HTTPException(status_code=400, detail=f"指令类型 '{data.command_type}' 已存在")

    item = manager.create(
        command_type=data.command_type,
        keywords=data.keywords,
        description=data.description,
        priority=data.priority,
        reply_type=data.reply_type,
        reply_content=data.reply_content
    )

    return APIResponse(
        code=0,
        message="创建成功",
        data={"id": item.id}
    )


@admin_router.put("/keywords/{item_id}", response_model=APIResponse)
async def update_keyword(item_id: int, data: KeywordUpdate):
    """更新关键词"""
    manager = get_keyword_manager()

    existing = manager.get_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="关键词不存在")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    item = manager.update(item_id, **update_data)

    return APIResponse(
        code=0,
        message="更新成功",
        data={"id": item.id}
    )


@admin_router.delete("/keywords/{item_id}", response_model=APIResponse)
async def delete_keyword(item_id: int):
    """删除关键词"""
    manager = get_keyword_manager()

    existing = manager.get_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="关键词不存在")

    success = manager.delete(item_id)

    return APIResponse(
        code=0,
        message="删除成功",
        data={"deleted": success}
    )


@admin_router.get("/keywords-dict")
async def get_keywords_dict():
    """
    获取关键词字典格式（用于前端展示或调试）
    """
    manager = get_keyword_manager()
    return manager.get_keywords_dict()


@admin_router.post("/keywords/validate")
async def validate_keyword(text: str):
    """
    测试关键词匹配
    用于验证配置是否正确
    """
    manager = get_keyword_manager()
    matched = manager.match_command(text)

    return {
        "input": text,
        "matched_command": matched,
        "all_keywords": manager.get_keywords_dict()
    }
