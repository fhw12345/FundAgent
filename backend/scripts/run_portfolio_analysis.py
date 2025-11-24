#!/usr/bin/env python3
"""
Standalone script for portfolio analysis.

This script can be run:
1. Locally: python scripts/run_portfolio_analysis.py
2. Docker Compose: docker compose run --rm portfolio-agent
3. Kubernetes CronJob: Scheduled automatically

Usage:
  # Analyze all users
  python scripts/run_portfolio_analysis.py

  # Analyze single user
  python scripts/run_portfolio_analysis.py --user-id user_123

  # Dry run (no DB writes)
  python scripts/run_portfolio_analysis.py --dry-run

  # Verbose logging
  python scripts/run_portfolio_analysis.py --verbose
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for local execution
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from src.agent.langgraph_react_agent import FinancialAnalysisReActAgent
from src.agent.portfolio_analysis_agent import PortfolioAnalysisAgent
from src.core.config import get_settings
from src.core.data.ticker_data_service import TickerDataService
from src.database.mongodb import MongoDB
from src.database.redis import RedisCache
from src.database.repositories.transaction_repository import TransactionRepository
from src.database.repositories.user_repository import UserRepository
from src.services.alpaca_data_service import AlpacaDataService
from src.services.alpaca_trading_service import AlpacaTradingService
from src.services.alphavantage_market_data import AlphaVantageMarketDataService
from src.services.credit_service import CreditService

logger = structlog.get_logger()


async def main():
    """Main execution function."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Run autonomous portfolio analysis")
    parser.add_argument(
        "--user-id",
        type=str,
        help="Analyze specific user only (default: all users)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't write results to DB",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info(
        "Portfolio analysis script started",
        user_filter=args.user_id,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Load settings
    settings = get_settings()

    # Initialize database connections
    mongodb = MongoDB()
    redis_cache = RedisCache()

    try:
        # Connect to databases
        logger.info("Connecting to databases", mongodb_url=settings.mongodb_url)
        await mongodb.connect(settings.mongodb_url)
        await redis_cache.connect(settings.redis_url)

        logger.info("Database connections established")

        # Initialize Alpha Vantage market data service (required)
        logger.info("Initializing Alpha Vantage market data service")
        market_service = AlphaVantageMarketDataService(settings=settings)

        # Initialize services (Alpaca is optional for portfolio analysis)
        alpaca_data_service = None
        trading_service = None
        if settings.alpaca_api_key and settings.alpaca_secret_key:
            try:
                alpaca_data_service = AlpacaDataService(settings=settings)
                trading_service = AlpacaTradingService(settings=settings)
                logger.info("Alpaca services initialized (data + trading)")
            except Exception as e:
                logger.warning(
                    "Alpaca services unavailable - continuing without order placement",
                    error=str(e),
                )
        else:
            logger.info("Alpaca API keys not configured - no order placement")

        ticker_service = (
            TickerDataService(
                redis_cache=redis_cache,
                alpaca_data_service=alpaca_data_service,
            )
            if alpaca_data_service
            else None
        )

        # Initialize ReAct agent
        logger.info("Initializing ReAct agent")
        react_agent = FinancialAnalysisReActAgent(
            settings=settings,
            ticker_data_service=ticker_service,
            market_service=market_service,
        )

        logger.info(
            "ReAct agent initialized",
            total_tools=len(react_agent.tools),
        )

        # Initialize credit service for usage tracking
        logger.info("Initializing credit service")
        user_repo = UserRepository(mongodb.get_collection("users"))
        transaction_repo = TransactionRepository(mongodb.get_collection("transactions"))
        credit_service = CreditService(
            user_repo=user_repo,
            transaction_repo=transaction_repo,
            mongodb=mongodb,
            settings=settings,
        )
        logger.info("Credit service initialized (portfolio agent usage tracking)")

        # Initialize portfolio analysis agent
        portfolio_agent = PortfolioAnalysisAgent(
            mongodb=mongodb,
            redis_cache=redis_cache,
            react_agent=react_agent,
            settings=settings,
            market_service=market_service,
            trading_service=trading_service,
            credit_service=credit_service,
        )

        # Run analysis
        if args.user_id:
            # Analyze single user
            logger.info("Analyzing single user", user_id=args.user_id)
            result = await portfolio_agent.analyze_user_portfolio(
                user_id=args.user_id,
                dry_run=args.dry_run,
            )
        else:
            # Analyze all users
            logger.info("Analyzing all users")
            result = await portfolio_agent.analyze_all_portfolios(
                dry_run=args.dry_run,
            )

        # Print summary
        print("\n" + "=" * 60)
        print("PORTFOLIO ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Run ID: {result.get('run_id', 'N/A')}")
        print(f"Users Analyzed: {result.get('users_analyzed', 0)}")
        print(f"Portfolios Analyzed: {result.get('portfolios_analyzed', 0)}")
        print(f"Errors: {len(result.get('errors', []))}")
        print(
            f"Duration: {result.get('metrics', {}).get('total_duration_seconds', 0):.2f}s"
        )
        print(f"Dry Run: {args.dry_run}")
        print("=" * 60)

        # Exit code
        if result.get("errors"):
            logger.warning(
                "Analysis completed with errors", errors_count=len(result["errors"])
            )
            sys.exit(1)
        else:
            logger.info("Analysis completed successfully")
            sys.exit(0)

    except Exception as e:
        logger.error(
            "Portfolio analysis failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        # Cleanup database connections
        logger.info("Cleaning up database connections")
        await mongodb.disconnect()
        await redis_cache.disconnect()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
