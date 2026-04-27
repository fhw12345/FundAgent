"""Repository for fund transactions and DCA plans."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

logger = structlog.get_logger()


class TransactionRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("user_id", 1), ("date", -1)])
        await self.collection.create_index([("user_id", 1), ("fund_code", 1), ("date", -1)])
        await self.collection.create_index("tx_id", unique=True)

    async def insert(self, tx: dict[str, Any]) -> dict[str, Any]:
        if "tx_id" not in tx:
            tx["tx_id"] = str(uuid4())
        if "created_at" not in tx:
            tx["created_at"] = datetime.now(timezone.utc)
        await self.collection.insert_one(tx)
        tx.pop("_id", None)
        logger.info("Transaction inserted", tx_id=tx["tx_id"], type=tx.get("tx_type"), code=tx.get("fund_code"))
        return tx

    async def list_for_user(
        self,
        user_id: str,
        fund_code: str | None = None,
        tx_type: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": user_id}
        if fund_code:
            query["fund_code"] = fund_code
        if tx_type:
            query["tx_type"] = tx_type
        cursor = self.collection.find(query).sort("date", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def delete(self, user_id: str, tx_id: str) -> bool:
        result = await self.collection.delete_one({"user_id": user_id, "tx_id": tx_id})
        return result.deleted_count > 0

    async def list_for_fund(self, user_id: str, fund_code: str) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {"user_id": user_id, "fund_code": fund_code}
        ).sort("date", 1)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def get_distinct_funds(self, user_id: str) -> list[str]:
        return await self.collection.distinct("fund_code", {"user_id": user_id})

    async def list_pending_due(self, before_date: datetime) -> list[dict[str, Any]]:
        """Find pending transactions whose confirm_date is on or before the given date."""
        cursor = self.collection.find({
            "status": "pending",
            "confirm_date": {"$lte": before_date},
        })
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def confirm_transaction(
        self, tx_id: str, actual_nav: float, actual_shares: float, confirmed_at: datetime
    ) -> bool:
        result = await self.collection.update_one(
            {"tx_id": tx_id},
            {"$set": {
                "status": "confirmed",
                "nav": actual_nav,
                "shares": actual_shares,
                "nav_source": "confirmed",
                "confirmed_at": confirmed_at,
            }},
        )
        return result.modified_count > 0

    async def mark_failed(self, tx_id: str) -> bool:
        result = await self.collection.update_one(
            {"tx_id": tx_id}, {"$set": {"status": "failed"}}
        )
        return result.modified_count > 0


class DCAPlanRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("user_id", 1), ("status", 1)])
        await self.collection.create_index("plan_id", unique=True)

    async def insert(self, plan: dict[str, Any]) -> dict[str, Any]:
        if "plan_id" not in plan:
            plan["plan_id"] = str(uuid4())
        if "created_at" not in plan:
            plan["created_at"] = datetime.now(timezone.utc)
        await self.collection.insert_one(plan)
        plan.pop("_id", None)
        return plan

    async def list_active(self) -> list[dict[str, Any]]:
        cursor = self.collection.find({"status": "active"})
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", -1)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def update_status(self, plan_id: str, status: str) -> bool:
        result = await self.collection.update_one(
            {"plan_id": plan_id}, {"$set": {"status": status}}
        )
        return result.modified_count > 0

    async def mark_executed(self, plan_id: str, executed_at: datetime) -> None:
        await self.collection.update_one(
            {"plan_id": plan_id}, {"$set": {"last_executed": executed_at}}
        )

    async def delete(self, user_id: str, plan_id: str) -> bool:
        result = await self.collection.delete_one({"user_id": user_id, "plan_id": plan_id})
        return result.deleted_count > 0
