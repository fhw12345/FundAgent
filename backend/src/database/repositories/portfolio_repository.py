"""Portfolio repository for fund holdings persistence."""

from datetime import datetime, timezone
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

logger = structlog.get_logger()


class PortfolioRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("user_id")
        await self.collection.create_index([("user_id", 1), ("updated_at", -1)])

    async def get_portfolio(self, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"user_id": user_id})

    async def upsert_portfolio(
        self, user_id: str, holdings: list[dict[str, Any]], source: str = "manual"
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "holdings": holdings,
            "source": source,
            "updated_at": now,
        }
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        logger.info(
            "Portfolio upserted",
            user_id=user_id,
            holding_count=len(holdings),
            source=source,
            upserted=result.upserted_id is not None,
        )
        return doc

    async def get_fund_codes(self, user_id: str) -> list[str]:
        portfolio = await self.get_portfolio(user_id)
        if not portfolio:
            return []
        return [h["fund_code"] for h in portfolio.get("holdings", []) if h.get("fund_code")]
