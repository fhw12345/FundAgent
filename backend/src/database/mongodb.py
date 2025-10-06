"""
MongoDB connection and operations.
Following Factor 3: External Dependencies as Services.
"""

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = structlog.get_logger()


class MongoDB:
    """MongoDB connection manager with async support."""

    def __init__(self) -> None:
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self, mongodb_url: str) -> None:
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(mongodb_url)

            # Extract database name from URL
            database_name = mongodb_url.split("/")[-1]
            self.database = self.client[database_name]

            # Test connection
            await self.client.admin.command("ping")

            logger.info("MongoDB connection established", database=database_name)

        except Exception as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    async def health_check(self) -> dict[str, bool | str]:
        """Check MongoDB connection health."""
        try:
            if not self.client:
                return {"connected": False, "error": "No client connection"}

            # Ping database
            await self.client.admin.command("ping")

            # Get server info
            server_info = await self.client.server_info()

            return {
                "connected": True,
                "version": server_info.get("version", "unknown"),
                "database": self.database.name if self.database is not None else "unknown",
            }

        except Exception as e:
            logger.error("MongoDB health check failed", error=str(e))
            return {"connected": False, "error": str(e)}

    def get_collection(self, collection_name: str):
        """Get a MongoDB collection."""
        if self.database is None:
            raise RuntimeError("Database connection not established")
        return self.database[collection_name]
