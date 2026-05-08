"""
公众号比价机器人主程序
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from api import wechat_router, admin_router
from services.price_service import PriceService
from core.logger import logger


class NoCacheMiddleware(BaseHTTPMiddleware):
    """禁用静态文件缓存的中间件"""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时
    logger.info("=" * 50)
    logger.info("🚀 公众号比价机器人启动中...")
    logger.info("=" * 50)

    settings = get_settings()
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"调试模式: {settings.DEBUG}")

    # 初始化价格服务
    try:
        await price_service.initialize()
        logger.info("✅ 价格服务初始化完成")
    except Exception as e:
        logger.error(f"❌ 价格服务初始化失败: {e}")
        raise

    yield

    # 关闭时
    logger.info("🛑 正在关闭服务...")
    await price_service.shutdown()
    logger.info("✅ 服务已关闭")


# 创建FastAPI应用
settings = get_settings()
app = FastAPI(
    title="公众号比价机器人",
    description="支持拼多多商品查询和优惠券搜索",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 价格服务实例
price_service = PriceService()

# 添加禁用缓存中间件（必须在静态文件之前）
app.add_middleware(NoCacheMiddleware)

# 注册路由
app.include_router(wechat_router)
app.include_router(admin_router)

# 静态文件（管理后台）- 使用绝对路径
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "公众号比价机器人",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "cache": "connected" if price_service.cache._redis else "disconnected",
    }


@app.get("/test/link")
async def test_link_parser(link: str):
    """
    测试链接解析（仅调试）
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="仅调试模式可用")

    from services.link_parser import LinkParser
    parser = LinkParser()

    platform, item_id = await parser.parse(link)

    return {
        "original_link": link,
        "platform": platform.value if platform else None,
        "item_id": item_id,
    }


@app.get("/test/product")
async def test_product_query(platform: str, item_id: str):
    """
    测试商品查询（仅调试）
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="仅调试模式可用")

    from models import PlatformType

    try:
        p = PlatformType(platform)
        product = await price_service.get_product(p, item_id)

        return {
            "success": True,
            "product": product.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
