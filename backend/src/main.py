"""
FastAPI application entry point for Financial Agent Backend.
Following Factor 11/12: Triggerable & Stateless design.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .api.admin import router as admin_router
from .api.analysis import router as analysis_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.feedback import router as feedback_router
from .api.health import router as health_router
from .api.market_data import router as market_data_router
from .core.config import get_settings
from .core.exceptions import AppError
from .database.mongodb import MongoDB
from .database.redis import RedisCache

# Set the root logger level to INFO so we can see detailed logs
logging.basicConfig(level=logging.INFO)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management for database connections."""
    settings = get_settings()

    logger.info("Starting Financial Agent Backend", environment=settings.environment)

    # Initialize database connections
    mongodb = MongoDB()
    redis_cache = RedisCache()

    try:
        await mongodb.connect(settings.mongodb_url)
        await redis_cache.connect(settings.redis_url)

        # Create database indexes for optimal query performance
        from .database.repositories.comment_repository import CommentRepository
        from .database.repositories.feedback_repository import FeedbackRepository
        from .database.repositories.refresh_token_repository import (
            RefreshTokenRepository,
        )

        refresh_token_repo = RefreshTokenRepository(
            mongodb.get_collection("refresh_tokens")
        )
        await refresh_token_repo.ensure_indexes()
        logger.info("Refresh token indexes created")

        feedback_repo = FeedbackRepository(mongodb.get_collection("feedback_items"))
        await feedback_repo.ensure_indexes()
        logger.info("Feedback item indexes created")

        comment_repo = CommentRepository(mongodb.get_collection("comments"))
        await comment_repo.ensure_indexes()
        logger.info("Comment indexes created")

        # Store in app state for dependency injection
        app.state.mongodb = mongodb
        app.state.redis = redis_cache

        logger.info("Database connections started")

        yield

    finally:
        # Cleanup database connections
        await mongodb.disconnect()
        await redis_cache.disconnect()
        logger.info("Database connections stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Financial Agent API",
        description="AI-Enhanced Financial Analysis Platform",
        version="0.1.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
        lifespan=lifespan,
    )

    # Security middleware - only in production
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )

    # CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # Global exception handler for custom app errors
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """
        Handle all custom AppError exceptions with proper HTTP status codes.

        This prevents DatabaseError, ConfigurationError, etc. from appearing as
        generic 500 errors, making debugging much faster.
        """
        error_dict = exc.to_dict()

        # Log error with full context
        logger.error(
            "Application error occurred",
            path=request.url.path,
            method=request.method,
            **error_dict,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_type": exc.error_type},
        )

    # Include routers
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(admin_router)  # Admin-only monitoring endpoints
    app.include_router(auth_router)
    app.include_router(analysis_router)
    app.include_router(market_data_router)
    app.include_router(chat_router)  # Persistent MongoDB-based chat
    app.include_router(feedback_router)  # Feedback & Community Roadmap platform

    @app.get("/")
    async def root():
        """Root endpoint for basic connectivity check."""
        return {
            "message": "Financial Agent API",
            "version": "0.1.0",
            "environment": settings.environment,
        }

    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # nosec B104 - Required for Docker container
        port=8000,
        reload=settings.environment == "development",
        log_config=None,  # Use structlog configuration
    )
