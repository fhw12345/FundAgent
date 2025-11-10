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
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.admin import router as admin_router
from .api.analysis import router as analysis_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.credits import router as credits_router
from .api.feedback import router as feedback_router
from .api.health import router as health_router
from .api.llm_models import router as llm_models_router
from .api.market_data import router as market_data_router
from .api.portfolio import router as portfolio_router
from .api.watchlist import router as watchlist_router
from .api.dependencies.rate_limit import limiter
from .core.config import get_settings
from .core.exceptions import AppError
from .database.mongodb import MongoDB
from .database.redis import RedisCache

# Set the root logger level to INFO so we can see detailed logs
logging.basicConfig(level=logging.INFO)

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
        from .database.repositories.chat_repository import ChatRepository
        from .database.repositories.comment_repository import CommentRepository
        from .database.repositories.feedback_repository import FeedbackRepository
        from .database.repositories.message_repository import MessageRepository
        from .database.repositories.refresh_token_repository import (
            RefreshTokenRepository,
        )
        from .database.repositories.tool_execution_repository import (
            ToolExecutionRepository,
        )
        from .database.repositories.transaction_repository import (
            TransactionRepository,
        )

        refresh_token_repo = RefreshTokenRepository(
            mongodb.get_collection("refresh_tokens")
        )
        await refresh_token_repo.ensure_indexes()
        logger.info("Refresh token indexes created")

        feedback_repo = FeedbackRepository(mongodb.get_collection("feedback_items"))
        await feedback_repo.ensure_indexes()

        comment_repo = CommentRepository(mongodb.get_collection("comments"))
        await comment_repo.ensure_indexes()

        transaction_repo = TransactionRepository(mongodb.get_collection("transactions"))
        await transaction_repo.ensure_indexes()

        message_repo = MessageRepository(mongodb.get_collection("messages"))
        await message_repo.ensure_indexes()
        logger.info("Message indexes created")

        # Phase 2 indexes: Chat and Tool Execution
        chat_repo = ChatRepository(mongodb.get_collection("chats"))
        await chat_repo.ensure_indexes()
        logger.info("Chat indexes created (symbol-per-chat pattern)")

        tool_execution_repo = ToolExecutionRepository(
            mongodb.get_collection("tool_executions")
        )
        await tool_execution_repo.ensure_indexes()
        logger.info("Tool execution indexes created (audit trail + cost tracking)")

        # Portfolio indexes: Holdings
        from .database.repositories.holding_repository import HoldingRepository

        holding_repo = HoldingRepository(mongodb.get_collection("holdings"))
        await holding_repo.ensure_indexes()
        logger.info("Holding indexes created (portfolio management)")

        # Watchlist indexes
        from .database.repositories.watchlist_repository import WatchlistRepository

        watchlist_repo = WatchlistRepository(mongodb.get_collection("watchlist"))
        await watchlist_repo.ensure_indexes()
        logger.info("Watchlist indexes created (symbol tracking)")

        # Portfolio order indexes (order audit trail)
        from .database.repositories.portfolio_order_repository import (
            PortfolioOrderRepository,
        )

        order_repo = PortfolioOrderRepository(mongodb.get_collection("portfolio_orders"))
        await order_repo.ensure_indexes()
        logger.info("Portfolio order indexes created (order audit trail)")

        # Initialize MCP tools for ReAct agent (if configured)
        # This loads 118 Alpha Vantage tools via MCP protocol
        from .agent.langgraph_react_agent import FinancialAnalysisReActAgent
        from .core.data.ticker_data_service import TickerDataService
        from .services.alpaca_data_service import AlpacaDataService
        from .services.alpaca_trading_service import AlpacaTradingService
        from .database.repositories.tool_execution_repository import ToolExecutionRepository
        from .services.tool_cache_wrapper import ToolCacheWrapper

        react_agent = None
        alpaca_trading_service = None
        try:
            # Create agent instance (will be cached as singleton in dependency injection)
            alpaca_data_service = AlpacaDataService(settings=settings)
            alpaca_trading_service = AlpacaTradingService(settings=settings)
            ticker_service = TickerDataService(
                redis_cache=redis_cache,
                alpaca_data_service=alpaca_data_service,
            )

            # Initialize tool execution tracking
            tool_exec_collection = mongodb.get_collection("tool_executions")
            tool_exec_repo = ToolExecutionRepository(tool_exec_collection)
            await tool_exec_repo.ensure_indexes()

            # Initialize tool cache wrapper for execution tracking
            tool_cache_wrapper = ToolCacheWrapper(
                redis_cache=redis_cache,
                tool_execution_repo=tool_exec_repo,
            )

            logger.info("Tool execution tracking initialized")

            # Create agent with tool cache wrapper
            react_agent = FinancialAnalysisReActAgent(
                settings=settings,
                ticker_data_service=ticker_service,
                tool_cache_wrapper=tool_cache_wrapper,
            )

            # Load MCP tools asynchronously (118 tools from Alpha Vantage)
            await react_agent.initialize_mcp_tools()

            # Store in app state for use in dependencies
            app.state.react_agent = react_agent
            logger.info("ReAct agent initialized with MCP tools")

        except Exception as e:
            logger.warning(
                "Failed to initialize ReAct agent with MCP tools - will use local tools only",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Initialize watchlist analyzer (manual trigger only, no auto-run)
        from .services.watchlist_analyzer import WatchlistAnalyzer

        watchlist_analyzer = WatchlistAnalyzer(
            watchlist_collection=mongodb.get_collection("watchlist"),
            messages_collection=mongodb.get_collection("messages"),
            chats_collection=mongodb.get_collection("chats"),
            redis_cache=redis_cache,
            agent=react_agent,  # Pass agent for LLM-based analysis
            trading_service=alpaca_trading_service,  # Pass trading service for order placement
            order_repository=order_repo,  # Pass order repository for MongoDB persistence
        )

        # Store in app state for manual triggering via API
        app.state.watchlist_analyzer = watchlist_analyzer
        logger.info("Watchlist analyzer initialized (manual trigger mode)" + (" with agent" if react_agent else " without agent"))

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

    # Rate limiting - SlowAPI integration
    app.state.limiter = limiter
    # Only add middleware in non-test environments (middleware breaks FastAPI TestClient)
    if settings.environment != "test":
        app.add_middleware(SlowAPIMiddleware)  # This middleware enforces rate limits

    # Custom rate limit exception handler that handles both RateLimitExceeded and connection errors
    @app.exception_handler(RateLimitExceeded)
    async def custom_rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle rate limit exceeded errors gracefully, including Redis connection failures."""
        # Check if this is a RateLimitExceeded exception
        if isinstance(exc, RateLimitExceeded):
            return JSONResponse(
                status_code=429,
                content={"error": f"Rate limit exceeded: {exc.detail}"},
                headers={"Retry-After": str(60)},
            )
        # Handle other exceptions (like ConnectionError from Redis)
        else:
            logger.warning(
                "Rate limiting error occurred",
                error=str(exc),
                error_type=type(exc).__name__,
                path=request.url.path,
            )
            # Allow request to proceed if Redis is unavailable (graceful degradation)
            return JSONResponse(
                status_code=503,
                content={"error": "Rate limiting temporarily unavailable"},
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
    app.include_router(portfolio_router)  # Portfolio holdings management
    app.include_router(watchlist_router)  # Watchlist symbol tracking
    app.include_router(credits_router)  # Token-based credit economy
    app.include_router(llm_models_router)  # LLM model selection and pricing
    app.include_router(feedback_router)  # Feedback & Community Roadmap platform

    @app.get("/")
    async def root() -> dict[str, str]:
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
