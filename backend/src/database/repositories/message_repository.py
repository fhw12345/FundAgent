"""
Message repository for conversation history.
Handles CRUD operations for message collection.
"""

from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ...models.message import Message, MessageCreate

logger = structlog.get_logger()


class MessageRepository:
    """Repository for message data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize message repository.

        Args:
            collection: MongoDB collection for messages
        """
        self.collection = collection

    async def ensure_indexes(self) -> None:
        """
        Create indexes for optimal query performance.
        Called during application startup.

        Note: Uses existing index names to avoid conflicts with previously created indexes.
        """
        await self.collection.create_index("chat_id", name="chat_id_1")
        await self.collection.create_index(
            [("chat_id", 1), ("timestamp", 1)], name="idx_chat_messages"
        )
        await self.collection.create_index(
            "metadata.transaction_id", sparse=True, name="metadata.transaction_id_1"
        )

        logger.info("Message indexes ensured")

    async def create(self, message_create: MessageCreate) -> Message:
        """
        Create a new message.

        Args:
            message_create: Message creation data

        Returns:
            Created message with generated ID
        """
        # Generate message_id
        import uuid

        message_id = f"msg_{uuid.uuid4().hex[:12]}"

        message = Message(
            message_id=message_id,
            chat_id=message_create.chat_id,
            role=message_create.role,
            content=message_create.content,
            source=message_create.source,
            timestamp=datetime.utcnow(),
            metadata=message_create.metadata,
        )

        # Convert to dict for MongoDB
        message_dict = message.model_dump()

        # Insert into database
        await self.collection.insert_one(message_dict)

        logger.info(
            "Message created",
            message_id=message_id,
            chat_id=message_create.chat_id,
            source=message_create.source,
        )

        return message

    async def get_by_chat(
        self,
        chat_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """
        Get messages for a chat.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip (for pagination)

        Returns:
            List of messages sorted by timestamp ascending
        """
        cursor = (
            self.collection.find({"chat_id": chat_id})
            .sort("timestamp", 1)  # Ascending (oldest first)
            .skip(offset)
            .limit(limit)
        )

        messages = []
        async for message_dict in cursor:
            # Remove MongoDB _id field
            message_dict.pop("_id", None)
            messages.append(Message(**message_dict))

        return messages

    async def get_by_chat_reverse(
        self,
        chat_id: str,
        limit: int = 100,
    ) -> list[Message]:
        """
        Get messages for a chat in reverse chronological order.
        Useful for finding recent analysis messages.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of messages to return

        Returns:
            List of messages sorted by timestamp descending (newest first)
        """
        cursor = (
            self.collection.find({"chat_id": chat_id})
            .sort("timestamp", -1)  # Descending (newest first)
            .limit(limit)
        )

        messages = []
        async for message_dict in cursor:
            # Remove MongoDB _id field
            message_dict.pop("_id", None)
            messages.append(Message(**message_dict))

        return messages

    async def get_fibonacci_messages(
        self,
        chat_id: str,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """
        Get Fibonacci analysis messages for a chat.
        Optionally filter by symbol.

        Args:
            chat_id: Chat identifier
            symbol: Optional symbol to filter by
            limit: Maximum number of messages to return

        Returns:
            List of Fibonacci messages sorted by timestamp descending
        """
        # Build query
        query = {
            "chat_id": chat_id,
            "source": "fibonacci",
        }

        if symbol:
            query["metadata.symbol"] = symbol

        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)

        messages = []
        async for message_dict in cursor:
            # Remove MongoDB _id field
            message_dict.pop("_id", None)
            messages.append(Message(**message_dict))

        return messages

    async def delete_by_chat(self, chat_id: str) -> int:
        """
        Delete all messages for a chat (cascade delete).

        Args:
            chat_id: Chat identifier

        Returns:
            Number of messages deleted
        """
        result = await self.collection.delete_many({"chat_id": chat_id})
        deleted_count: int = result.deleted_count

        logger.info("Messages deleted", chat_id=chat_id, count=deleted_count)

        return deleted_count

    async def count_by_chat(self, chat_id: str) -> int:
        """
        Count messages in a chat.

        Args:
            chat_id: Chat identifier

        Returns:
            Message count
        """
        count: int = await self.collection.count_documents({"chat_id": chat_id})
        return count

    async def get_by_transaction_id(self, transaction_id: str) -> Message | None:
        """
        Get message by transaction ID (for reconciliation).

        Args:
            transaction_id: Transaction identifier from metadata

        Returns:
            Message if found, None otherwise
        """
        message_dict = await self.collection.find_one(
            {"metadata.transaction_id": transaction_id}
        )

        if not message_dict:
            return None

        # Remove MongoDB _id field
        message_dict.pop("_id", None)

        return Message(**message_dict)
