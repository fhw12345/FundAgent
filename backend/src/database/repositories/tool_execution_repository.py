"""
Tool execution repository for tracking all tool calls.

Stores execution records for both 1st-party and 3rd-party (MCP) tools.
"""

from datetime import datetime
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.tool_execution import ToolExecution

logger = structlog.get_logger()


class ToolExecutionRepository:
    """Repository for tool execution data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize tool execution repository.

        Args:
            collection: MongoDB collection for tool_executions
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create indexes for optimal query performance.
        Called during application startup.

        Indexes:
        1. analysis_id + started_at: For audit trail (tool sequence per analysis)
        2. chat_id + started_at: For chat history
        3. user_id + started_at: For cost tracking queries
        4. tool_source + is_paid_api: For cost aggregation by source
        """
        # Index for analysis audit trail (get tool sequence)
        await self.collection.create_index(
            [("analysis_id", 1), ("started_at", 1)], name="idx_analysis_tools"
        )

        # Index for chat tool history
        await self.collection.create_index(
            [("chat_id", 1), ("started_at", -1)], name="idx_chat_tools"
        )

        # Index for cost tracking by user
        await self.collection.create_index(
            [("user_id", 1), ("started_at", -1)], name="idx_user_cost"
        )

        # Index for cost aggregation by tool source
        await self.collection.create_index(
            [("tool_source", 1), ("is_paid_api", 1)], name="idx_tool_cost"
        )

        logger.info("Tool execution indexes ensured")

    async def create(self, execution: ToolExecution) -> ToolExecution:
        """
        Create a new tool execution record.

        Args:
            execution: Tool execution data

        Returns:
            Created tool execution
        """
        # Convert to dict for MongoDB
        execution_dict = execution.model_dump()

        # Insert into database
        await self.collection.insert_one(execution_dict)

        logger.info(
            "Tool execution created",
            execution_id=execution.execution_id,
            tool_name=execution.tool_name,
            tool_source=execution.tool_source,
            status=execution.status,
        )

        return execution

    async def get(self, execution_id: str) -> ToolExecution | None:
        """
        Get tool execution by ID.

        Args:
            execution_id: Execution identifier

        Returns:
            ToolExecution if found, None otherwise
        """
        execution_dict = await self.collection.find_one({"execution_id": execution_id})

        if not execution_dict:
            return None

        # Remove MongoDB _id field
        execution_dict.pop("_id", None)

        return ToolExecution(**execution_dict)

    async def list_by_analysis(
        self, analysis_id: str, limit: int = 100
    ) -> list[ToolExecution]:
        """
        List all tool executions for an analysis workflow.

        Used for audit trail and cost tracking.

        Args:
            analysis_id: Analysis workflow ID
            limit: Maximum number of executions to return

        Returns:
            List of tool executions sorted by started_at ascending
        """
        cursor = (
            self.collection.find({"analysis_id": analysis_id})
            .sort("started_at", 1)
            .limit(limit)
        )

        executions = []
        async for execution_dict in cursor:
            # Remove MongoDB _id field
            execution_dict.pop("_id", None)
            executions.append(ToolExecution(**execution_dict))

        return executions

    async def list_by_chat(self, chat_id: str, limit: int = 100) -> list[ToolExecution]:
        """
        List all tool executions for a chat.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of executions to return

        Returns:
            List of tool executions sorted by started_at descending
        """
        cursor = (
            self.collection.find({"chat_id": chat_id})
            .sort("started_at", -1)
            .limit(limit)
        )

        executions = []
        async for execution_dict in cursor:
            # Remove MongoDB _id field
            execution_dict.pop("_id", None)
            executions.append(ToolExecution(**execution_dict))

        return executions

    async def get_cost_summary(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """
        Get cost summary for user within date range.

        Args:
            user_id: User identifier
            start_date: Start datetime
            end_date: End datetime

        Returns:
            Cost summary dict:
            {
                "total_executions": 100,
                "total_cost": 0.004,
                "cache_hit_rate": 0.75,
                "by_tool_source": {
                    "mcp_alphavantage": {"calls": 80, "cost": 0.0032},
                    "1st_party": {"calls": 20, "cost": 0.0}
                }
            }
        """
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "started_at": {"$gte": start_date, "$lte": end_date},
                }
            },
            {
                "$group": {
                    "_id": "$tool_source",
                    "total_calls": {"$sum": 1},
                    "total_cost": {"$sum": "$api_cost"},
                    "cache_hits": {"$sum": {"$cond": ["$cache_hit", 1, 0]}},
                    "successful_calls": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    },
                }
            },
        ]

        results = await self.collection.aggregate(pipeline).to_list(100)

        # Aggregate results
        total_executions = sum(r["total_calls"] for r in results)
        total_cost = sum(r["total_cost"] for r in results)
        total_cache_hits = sum(r["cache_hits"] for r in results)

        by_tool_source = {
            r["_id"]: {
                "calls": r["total_calls"],
                "cost": r["total_cost"],
                "cache_hits": r["cache_hits"],
                "successful_calls": r["successful_calls"],
            }
            for r in results
        }

        return {
            "total_executions": total_executions,
            "total_cost": total_cost,
            "cache_hit_rate": (
                total_cache_hits / total_executions if total_executions > 0 else 0.0
            ),
            "by_tool_source": by_tool_source,
        }
