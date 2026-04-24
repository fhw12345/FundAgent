"""FundAgent Backend — FastAPI entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.admin import router as admin_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.dependencies.rate_limit import limiter
from .api.dependencies.timing_middleware import TimingMiddleware
from .api.health import router as health_router
from .api.llm_models import router as llm_models_router
from .api.portfolio import router as portfolio_router
from .api.quarterly_report import router as quarterly_report_router
from .core.config import get_settings
from .core.exceptions import AppError
from .database.mongodb import MongoDB
from .database.redis import RedisCache

logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("Starting FundAgent Backend", environment=settings.environment)

    mongodb = MongoDB()
    redis_cache = RedisCache()

    try:
        await mongodb.connect(settings.mongodb_url)
        await redis_cache.connect(settings.redis_url)

        from .database.repositories.chat_repository import ChatRepository
        from .database.repositories.message_repository import MessageRepository
        from .database.repositories.refresh_token_repository import RefreshTokenRepository

        refresh_token_repo = RefreshTokenRepository(mongodb.get_collection("refresh_tokens"))
        await refresh_token_repo.ensure_indexes()

        message_repo = MessageRepository(mongodb.get_collection("messages"))
        await message_repo.ensure_indexes()

        chat_repo = ChatRepository(mongodb.get_collection("chats"))
        await chat_repo.ensure_indexes()

        from .database.repositories.portfolio_repository import PortfolioRepository

        portfolio_repo = PortfolioRepository(mongodb.get_collection("portfolios"))
        await portfolio_repo.ensure_indexes()

        # Initialize ReAct agent
        react_agent = None
        try:
            from .agent.langgraph_react_agent import FinancialAnalysisReActAgent

            react_agent = FinancialAnalysisReActAgent(
                settings=settings,
                redis_cache=redis_cache,
            )
            app.state.react_agent = react_agent
            logger.info("ReAct agent initialized")
        except Exception as e:
            logger.warning("Failed to initialize ReAct agent", error=str(e))

        app.state.mongodb = mongodb
        app.state.redis = redis_cache

        logger.info("Database connections started")
        yield

    finally:
        await mongodb.disconnect()
        await redis_cache.disconnect()
        logger.info("Database connections stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="FundAgent API",
        description="AI-Powered Chinese Mutual Fund Analysis",
        version="0.11.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
        lifespan=lifespan,
    )

    if settings.environment == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    if settings.environment != "test":
        app.add_middleware(TimingMiddleware, log_all_requests=False, slow_threshold_ms=500.0)

    app.state.limiter = limiter
    if settings.environment != "test":
        app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def custom_rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, RateLimitExceeded):
            return JSONResponse(
                status_code=429,
                content={"error": f"Rate limit exceeded: {exc.detail}"},
                headers={"Retry-After": str(60)},
            )
        return JSONResponse(status_code=503, content={"error": "Rate limiting temporarily unavailable"})

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.error("Application error", path=request.url.path, **exc.to_dict())
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "error_type": exc.error_type})

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(llm_models_router)
    app.include_router(portfolio_router)
    app.include_router(quarterly_report_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "FundAgent API", "version": "0.11.0", "environment": settings.environment}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.environment == "development", log_config=None)  # nosec B104
