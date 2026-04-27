"""Repository for background job execution history (落盘 tracking)."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

logger = structlog.get_logger()


class JobRunRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("job_name", 1), ("started_at", -1)])
        await self.collection.create_index("run_id", unique=True)
        # TTL: keep 30 days of history
        await self.collection.create_index("started_at", expireAfterSeconds=30 * 24 * 3600)

    async def start(self, job_name: str) -> str:
        run_id = str(uuid4())
        await self.collection.insert_one({
            "run_id": run_id,
            "job_name": job_name,
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
            "status": "running",
            "items_processed": 0,
            "error": None,
        })
        return run_id

    async def finish(
        self,
        run_id: str,
        status: str,
        items_processed: int = 0,
        error: str | None = None,
    ) -> None:
        await self.collection.update_one(
            {"run_id": run_id},
            {"$set": {
                "finished_at": datetime.now(timezone.utc),
                "status": status,
                "items_processed": items_processed,
                "error": error,
            }},
        )

    async def list_recent(
        self, job_name: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if job_name:
            query["job_name"] = job_name
        cursor = self.collection.find(query).sort("started_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def latest_by_job(self) -> list[dict[str, Any]]:
        """Latest run per job_name — for dashboard summary."""
        pipeline = [
            {"$sort": {"started_at": -1}},
            {"$group": {
                "_id": "$job_name",
                "run_id": {"$first": "$run_id"},
                "started_at": {"$first": "$started_at"},
                "finished_at": {"$first": "$finished_at"},
                "status": {"$first": "$status"},
                "items_processed": {"$first": "$items_processed"},
                "error": {"$first": "$error"},
            }},
            {"$project": {"_id": 0, "job_name": "$_id", "run_id": 1, "started_at": 1,
                          "finished_at": 1, "status": 1, "items_processed": 1, "error": 1}},
        ]
        return [doc async for doc in self.collection.aggregate(pipeline)]
