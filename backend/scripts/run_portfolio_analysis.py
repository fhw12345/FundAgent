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

# Add src to path for local execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from src.agent.langgraph_react_agent import FinancialAnalysisReActAgent
from src.agent.portfolio_analysis_agent import PortfolioAnalysisAgent
from src.core.config import get_settings
from src.core.data.ticker_data_service import TickerDataService
from src.database.mongodb import MongoDB
from src.database.redis import RedisCache
from src.services.alpaca_data_service import AlpacaDataService

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

        # Initialize services (Alpaca is optional for portfolio analysis)
        alpaca_data_service = None
        if settings.alpaca_api_key and settings.alpaca_secret_key:
            try:
                alpaca_data_service = AlpacaDataService(settings=settings)
                logger.info("Alpaca data service initialized")
            except Exception as e:
                logger.warning(
                    "Alpaca data service unavailable - continuing without it",
                    error=str(e),
                )
        else:
            logger.info("Alpaca API keys not configured - skipping")

        ticker_service = (
            TickerDataService(
                redis_cache=redis_cache,
                alpaca_data_service=alpaca_data_service,
            )
            if alpaca_data_service
            else None
        )

        # Initialize ReAct agent with MCP tools
        logger.info("Initializing ReAct agent with MCP tools")
        react_agent = FinancialAnalysisReActAgent(
            settings=settings,
            ticker_data_service=ticker_service,
        )

        # Load MCP tools (118 tools from Alpha Vantage)
        await react_agent.initialize_mcp_tools()

        logger.info(
            "ReAct agent initialized",
            total_tools=len(react_agent.tools),
            mcp_enabled=react_agent.mcp_client is not None,
        )

        # Initialize portfolio analysis agent
        portfolio_agent = PortfolioAnalysisAgent(
            mongodb=mongodb,
            redis_cache=redis_cache,
            react_agent=react_agent,
            settings=settings,
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
