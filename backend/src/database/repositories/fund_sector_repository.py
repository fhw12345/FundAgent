"""Repository for fund → sector mapping cache."""

from datetime import datetime, timezone
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

logger = structlog.get_logger()


class FundSectorRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("fund_code", unique=True)

    async def get(self, fund_code: str) -> list[str] | None:
        doc = await self.collection.find_one({"fund_code": fund_code})
        if not doc:
            return None
        sectors = doc.get("sectors")
        return sectors if isinstance(sectors, list) else None

    async def upsert(self, fund_code: str, fund_name: str, sectors: list[str]) -> None:
        await self.collection.update_one(
            {"fund_code": fund_code},
            {"$set": {
                "fund_code": fund_code,
                "fund_name": fund_name,
                "sectors": sectors,
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

    async def get_all_map(self) -> dict[str, list[str]]:
        cursor = self.collection.find({}, {"_id": 0, "fund_code": 1, "sectors": 1})
        result: dict[str, list[str]] = {}
        async for doc in cursor:
            code = doc.get("fund_code")
            sectors = doc.get("sectors")
            if isinstance(code, str) and isinstance(sectors, list):
                result[code] = sectors
        return result
