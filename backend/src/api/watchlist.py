"""
Watchlist API endpoints for managing watched stocks.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from ..database.mongodb import MongoDB
from ..database.repositories.watchlist_repository import WatchlistRepository
from ..models.watchlist import WatchlistItem, WatchlistItemCreate
from ..services.alphavantage_market_data import AlphaVantageMarketDataService
from .dependencies.auth import get_current_user_id, get_mongodb, require_admin
from .dependencies.portfolio_deps import get_market_service
from .dependencies.rate_limit import limiter

logger = structlog.get_logger()

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.post("", response_model=WatchlistItem, status_code=201)
@limiter.limit("30/minute")  # Write operation - admin only
async def add_to_watchlist(
    request: Request,
    item: WatchlistItemCreate,
    _: None = Depends(require_admin),  # Admin only
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    mongodb: MongoDB = Depends(get_mongodb),
    market_service: AlphaVantageMarketDataService = Depends(get_market_service),
) -> WatchlistItem:
    """
    Add a symbol to watchlist for automated analysis.

    **Admin only** - Requires admin privileges to manage watchlist.

    **Symbol Validation** - Verifies symbol exists in market via AlphaVantage API.

    Args:
        item: Watchlist item creation data
        user_id: Authenticated user ID (from JWT)
        mongodb: MongoDB instance
        market_service: Market data service for symbol validation

    Returns:
        Created watchlist item

    Raises:
        HTTPException: 400 if symbol not found, 403 if not admin, 409 if symbol already in watchlist
    """
    try:
        # Validate symbol exists in market using AlphaVantage SYMBOL_SEARCH
        symbol_upper = item.symbol.upper()
        logger.info(
            "Validating symbol before adding to watchlist",
            user_id=user_id,
            symbol=symbol_upper,
        )

        try:
            search_results = await market_service.search_symbols(symbol_upper, limit=5)

            # Debug: Log search results for troubleshooting
            logger.debug(
                "Symbol search results",
                symbol=symbol_upper,
                results=[
                    {
                        "symbol": r.get("symbol"),
                        "name": r.get("name"),
                        "match_score": r.get("match_score"),
                    }
                    for r in search_results[:3]
                ],
            )

            # Check if exact match exists (case-insensitive)
            exact_match = None
            for result in search_results:
                if result.get("symbol", "").upper() == symbol_upper:
                    exact_match = result
                    break

            # Fallback: Accept high-confidence match (score >= 0.9)
            if not exact_match and search_results:
                first_result = search_results[0]
                match_score = first_result.get("match_score", 0.0)
                if match_score >= 0.9:
                    logger.info(
                        "Using high-confidence match as fallback",
                        user_id=user_id,
                        requested=symbol_upper,
                        matched=first_result.get("symbol"),
                        score=match_score,
                    )
                    exact_match = first_result

            # Final fallback: Try GLOBAL_QUOTE for direct validation
            if not exact_match:
                try:
                    quote = await market_service.get_quote(symbol_upper)
                    if quote and quote.get("price"):
                        logger.info(
                            "Symbol validated via GLOBAL_QUOTE fallback",
                            user_id=user_id,
                            symbol=symbol_upper,
                            price=quote.get("price"),
                        )
                        exact_match = {
                            "symbol": symbol_upper,
                            "name": "Verified via real-time quote",
                        }
                except Exception as quote_error:
                    logger.debug(
                        "GLOBAL_QUOTE fallback failed",
                        symbol=symbol_upper,
                        error=str(quote_error),
                    )

            if not exact_match:
                logger.warning(
                    "Symbol validation failed - not found in market",
                    user_id=user_id,
                    symbol=symbol_upper,
                    search_results_count=len(search_results),
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Symbol '{symbol_upper}' not found in market. Please verify the ticker symbol.",
                )

            # Log successful validation with company name
            company_name = exact_match.get("name", "Unknown")
            logger.info(
                "Symbol validated successfully",
                user_id=user_id,
                symbol=symbol_upper,
                company_name=company_name,
            )

        except HTTPException:
            raise  # Re-raise 400 validation errors
        except Exception as validation_error:
            # Log validation service error but don't block (fail open)
            logger.warning(
                "Symbol validation service unavailable - allowing symbol anyway",
                user_id=user_id,
                symbol=symbol_upper,
                error=str(validation_error),
                error_type=type(validation_error).__name__,
            )
            # Continue without validation if service is down

        # Create watchlist item (use uppercase symbol)
        item.symbol = symbol_upper
        watchlist_collection = mongodb.get_collection("watchlist")
        watchlist_repo = WatchlistRepository(watchlist_collection)

        watchlist_item = await watchlist_repo.create(user_id, item)

        logger.info(
            "Watchlist item added",
            user_id=user_id,
            symbol=watchlist_item.symbol,
            watchlist_id=watchlist_item.watchlist_id,
        )

        return watchlist_item

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=f"Symbol {item.symbol.upper()} is already in your watchlist",
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions (validation errors, auth errors)
    except Exception as e:
        logger.error(
            "Failed to add watchlist item",
            user_id=user_id,
            symbol=item.symbol,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to add symbol to watchlist. Please try again later.",
        )


@router.get("", response_model=list[WatchlistItem])
@limiter.limit("60/minute")  # Standard read operation
async def get_watchlist(
    request: Request,
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    mongodb: MongoDB = Depends(get_mongodb),
) -> list[WatchlistItem]:
    """
    Get all symbols in user's watchlist.

    Args:
        user_id: Authenticated user ID
        mongodb: MongoDB instance

    Returns:
        List of watchlist items sorted by added_at descending
    """
    try:
        watchlist_collection = mongodb.get_collection("watchlist")
        watchlist_repo = WatchlistRepository(watchlist_collection)

        items = await watchlist_repo.get_by_user(user_id)

        logger.info("Watchlist retrieved", user_id=user_id, count=len(items))

        return items

    except Exception as e:
        logger.error(
            "Failed to get watchlist",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve watchlist. Please try again later.",
        )


@router.delete("/{watchlist_id}", status_code=204)
@limiter.limit("30/minute")  # Write operation - admin only
async def remove_from_watchlist(
    request: Request,
    watchlist_id: str,
    _: None = Depends(require_admin),  # Admin only
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """
    Remove a symbol from watchlist.

    **Admin only** - Requires admin privileges to manage watchlist.

    Args:
        watchlist_id: Watchlist item identifier
        user_id: Authenticated user ID (from JWT)
        mongodb: MongoDB instance

    Raises:
        HTTPException: 403 if not admin, 404 if item not found
    """
    try:
        watchlist_collection = mongodb.get_collection("watchlist")
        watchlist_repo = WatchlistRepository(watchlist_collection)

        deleted = await watchlist_repo.delete(watchlist_id, user_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        logger.info(
            "Watchlist item removed", user_id=user_id, watchlist_id=watchlist_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to remove watchlist item",
            user_id=user_id,
            watchlist_id=watchlist_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to remove symbol from watchlist. Please try again later.",
        )


@router.post("/analyze", status_code=202)
@limiter.limit("2/minute")  # CRITICAL: Expensive LLM analysis - very restrictive
async def trigger_watchlist_analysis(
    request: Request,
    _: None = Depends(require_admin),  # Admin only
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
) -> dict:
    """
    Manually trigger analysis for all watchlist symbols.

    **Admin only** - Requires admin privileges to trigger expensive LLM analysis.

    This runs the watchlist analyzer once (not continuously).

    Args:
        request: FastAPI request (to access app.state)
        user_id: Authenticated user ID (from JWT)

    Returns:
        Status message indicating analysis has started

    Raises:
        HTTPException: 403 if not admin, 500 if analysis fails
    """
    try:
        # Get analyzer from app state
        if not hasattr(request.app.state, "watchlist_analyzer"):
            raise HTTPException(
                status_code=500, detail="Watchlist analyzer not initialized"
            )

        analyzer = request.app.state.watchlist_analyzer

        # Run one analysis cycle (force=True to analyze all symbols)
        logger.info("Manual watchlist analysis triggered", user_id=user_id)
        await analyzer.run_analysis_cycle(force=True)

        return {
            "status": "analysis_started",
            "message": "Watchlist analysis has been triggered",
        }

    except Exception as e:
        logger.error(
            "Failed to trigger watchlist analysis",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to trigger watchlist analysis. Please try again later.",
        )
