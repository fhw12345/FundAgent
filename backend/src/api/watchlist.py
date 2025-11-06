"""
Watchlist API endpoints for managing watched stocks.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from ..database.mongodb import MongoDB
from ..database.repositories.watchlist_repository import WatchlistRepository
from ..models.watchlist import WatchlistItem, WatchlistItemCreate
from .dependencies.auth import get_mongodb

logger = structlog.get_logger()

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.post("", response_model=WatchlistItem, status_code=201)
async def add_to_watchlist(
    item: WatchlistItemCreate,
    user_id: str = Depends(lambda: "default_user"),  # TODO: Replace with actual auth
    mongodb: MongoDB = Depends(get_mongodb),
) -> WatchlistItem:
    """
    Add a symbol to user's watchlist.

    Args:
        item: Watchlist item creation data
        user_id: Authenticated user ID
        mongodb: MongoDB instance

    Returns:
        Created watchlist item

    Raises:
        HTTPException: If symbol already in watchlist or validation fails
    """
    try:
        watchlist_collection = mongodb.get_collection("watchlist")
        watchlist_repo = WatchlistRepository(watchlist_collection)

        watchlist_item = await watchlist_repo.create(user_id, item)

        logger.info(
            "Watchlist item added",
            user_id=user_id,
            symbol=watchlist_item.symbol,
            watchlist_id=watchlist_item.watchlist_id
        )

        return watchlist_item

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=f"Symbol {item.symbol} is already in your watchlist"
        )
    except Exception as e:
        logger.error(
            "Failed to add watchlist item",
            user_id=user_id,
            symbol=item.symbol,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add watchlist item: {str(e)}"
        )


@router.get("", response_model=list[WatchlistItem])
async def get_watchlist(
    user_id: str = Depends(lambda: "default_user"),  # TODO: Replace with actual auth
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

        logger.info(
            "Watchlist retrieved",
            user_id=user_id,
            count=len(items)
        )

        return items

    except Exception as e:
        logger.error(
            "Failed to get watchlist",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get watchlist: {str(e)}"
        )


@router.delete("/{watchlist_id}", status_code=204)
async def remove_from_watchlist(
    watchlist_id: str,
    user_id: str = Depends(lambda: "default_user"),  # TODO: Replace with actual auth
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """
    Remove a symbol from user's watchlist.

    Args:
        watchlist_id: Watchlist item identifier
        user_id: Authenticated user ID
        mongodb: MongoDB instance

    Raises:
        HTTPException: If item not found or deletion fails
    """
    try:
        watchlist_collection = mongodb.get_collection("watchlist")
        watchlist_repo = WatchlistRepository(watchlist_collection)

        deleted = await watchlist_repo.delete(watchlist_id, user_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Watchlist item not found"
            )

        logger.info(
            "Watchlist item removed",
            user_id=user_id,
            watchlist_id=watchlist_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to remove watchlist item",
            user_id=user_id,
            watchlist_id=watchlist_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove watchlist item: {str(e)}"
        )


@router.post("/analyze", status_code=202)
async def trigger_watchlist_analysis(
    request: Request,
    user_id: str = Depends(lambda: "default_user"),  # TODO: Replace with actual auth
) -> dict:
    """
    Manually trigger analysis for all watchlist symbols.

    This runs the watchlist analyzer once (not continuously).

    Args:
        request: FastAPI request (to access app.state)
        user_id: Authenticated user ID

    Returns:
        Status message with count of analyzed symbols

    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Get analyzer from app state
        if not hasattr(request.app.state, "watchlist_analyzer"):
            raise HTTPException(
                status_code=500,
                detail="Watchlist analyzer not initialized"
            )

        analyzer = request.app.state.watchlist_analyzer

        # Run one analysis cycle (force=True to analyze all symbols)
        logger.info("Manual watchlist analysis triggered", user_id=user_id)
        await analyzer.run_analysis_cycle(force=True)

        return {
            "status": "analysis_started",
            "message": "Watchlist analysis has been triggered"
        }

    except Exception as e:
        logger.error(
            "Failed to trigger watchlist analysis",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger analysis: {str(e)}"
        )
