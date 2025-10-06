"""
Chat repository for conversation management.
Handles CRUD operations for chat collection with UI state management.
"""

from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorCollection
import structlog

from ...models.chat import Chat, ChatCreate, ChatUpdate, UIState

logger = structlog.get_logger()


class ChatRepository:
    """Repository for chat data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize chat repository.

        Args:
            collection: MongoDB collection for chats
        """
        self.collection = collection

    async def create(self, chat_create: ChatCreate) -> Chat:
        """
        Create a new chat.

        Args:
            chat_create: Chat creation data

        Returns:
            Created chat with generated ID
        """
        # Generate chat_id
        import uuid
        chat_id = f"chat_{uuid.uuid4().hex[:12]}"

        chat = Chat(
            chat_id=chat_id,
            user_id=chat_create.user_id,
            title=chat_create.title,
            is_archived=False,
            ui_state=UIState(),  # Default empty UI state
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=None,
        )

        # Convert to dict for MongoDB
        chat_dict = chat.model_dump()

        # Insert into database
        await self.collection.insert_one(chat_dict)

        logger.info("Chat created", chat_id=chat_id, user_id=chat_create.user_id)

        return chat

    async def get(self, chat_id: str) -> Chat | None:
        """
        Get chat by ID.

        Args:
            chat_id: Chat identifier

        Returns:
            Chat if found, None otherwise
        """
        chat_dict = await self.collection.find_one({"chat_id": chat_id})

        if not chat_dict:
            return None

        # Remove MongoDB _id field
        chat_dict.pop("_id", None)

        return Chat(**chat_dict)

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        include_archived: bool = False,
    ) -> list[Chat]:
        """
        List all chats for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of chats to return
            include_archived: Whether to include archived chats

        Returns:
            List of chats sorted by last_message_at descending
        """
        # Build query
        query = {"user_id": user_id}
        if not include_archived:
            query["is_archived"] = False

        # Find chats
        cursor = self.collection.find(query).sort("last_message_at", -1).limit(limit)

        chats = []
        async for chat_dict in cursor:
            # Remove MongoDB _id field
            chat_dict.pop("_id", None)
            chats.append(Chat(**chat_dict))

        return chats

    async def update(self, chat_id: str, chat_update: ChatUpdate) -> Chat | None:
        """
        Update chat metadata.

        Args:
            chat_id: Chat identifier
            chat_update: Fields to update

        Returns:
            Updated chat if found, None otherwise
        """
        # Build update dict (only include non-None fields)
        update_dict = {"updated_at": datetime.utcnow()}

        if chat_update.title is not None:
            update_dict["title"] = chat_update.title

        if chat_update.is_archived is not None:
            update_dict["is_archived"] = chat_update.is_archived

        if chat_update.ui_state is not None:
            update_dict["ui_state"] = chat_update.ui_state.model_dump()

        # Update in database
        result = await self.collection.find_one_and_update(
            {"chat_id": chat_id},
            {"$set": update_dict},
            return_document=True,
        )

        if not result:
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        logger.info("Chat updated", chat_id=chat_id, fields=list(update_dict.keys()))

        return Chat(**result)

    async def update_ui_state(self, chat_id: str, ui_state: UIState) -> Chat | None:
        """
        Update chat UI state.

        Args:
            chat_id: Chat identifier
            ui_state: New UI state

        Returns:
            Updated chat if found, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"chat_id": chat_id},
            {
                "$set": {
                    "ui_state": ui_state.model_dump(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )

        if not result:
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        logger.info("Chat UI state updated", chat_id=chat_id, symbol=ui_state.current_symbol)

        return Chat(**result)

    async def update_last_message_at(self, chat_id: str) -> Chat | None:
        """
        Update chat's last message timestamp.

        Args:
            chat_id: Chat identifier

        Returns:
            Updated chat if found, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"chat_id": chat_id},
            {
                "$set": {
                    "last_message_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )

        if not result:
            return None

        # Remove MongoDB _id field
        result.pop("_id", None)

        return Chat(**result)

    async def delete(self, chat_id: str) -> bool:
        """
        Delete a chat (hard delete).

        Args:
            chat_id: Chat identifier

        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one({"chat_id": chat_id})

        if result.deleted_count > 0:
            logger.info("Chat deleted", chat_id=chat_id)
            return True

        return False
