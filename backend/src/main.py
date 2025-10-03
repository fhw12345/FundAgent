"""
FastAPI application entry point for Financial Agent Backend.
Following Factor 11/12: Triggerable & Stateless design.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .api.health import router as health_router
from .api.analysis import router as analysis_router
from .api.market_data import router as market_data_router
from .core.config import get_settings
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

        # Store in app state for dependency injection
        app.state.mongodb = mongodb
        app.state.redis = redis_cache

        logger.info("Database connections established")

        yield

    finally:
        # Cleanup connections
        await mongodb.disconnect()
        await redis_cache.disconnect()
        logger.info("Database connections closed")


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
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(analysis_router)
    app.include_router(market_data_router)

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
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_config=None,  # Use structlog configuration
    )
