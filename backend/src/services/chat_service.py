"""
Chat service for managing conversations with LLM.
Business logic layer coordinating chats, messages, and LLM interactions.
"""

from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from ..core.config import Settings
from ..core.exceptions import NotFoundError, ValidationError
from ..database.repositories.chat_repository import ChatRepository
from ..database.repositories.message_repository import MessageRepository
from ..models.chat import Chat, ChatCreate, ChatUpdate, UIState
from ..models.message import Message, MessageCreate, MessageMetadata

logger = structlog.get_logger()


class ChatTitleResponse(BaseModel):
    """Structured LLM response for title generation."""

    title: str = Field(
        ...,
        max_length=50,
        description="Concise chat title (e.g., 'AAPL Fibonacci Analysis')",
    )
    response: str = Field(..., description="Full analysis response")


class ChatService:
    """Service for chat and message management with LLM integration."""

    def __init__(
        self,
        chat_repo: ChatRepository,
        message_repo: MessageRepository,
        settings: Settings,
    ):
        """
        Initialize chat service.

        Args:
            chat_repo: Repository for chat data access
            message_repo: Repository for message data access
            settings: Application settings
        """
        self.chat_repo = chat_repo
        self.message_repo = message_repo
        self.settings = settings

    async def create_chat(self, user_id: str, title: str = "New Chat") -> Chat:
        """
        Create a new chat.

        Args:
            user_id: User identifier
            title: Chat title (default: "New Chat")

        Returns:
            Created chat
        """
        chat = await self.chat_repo.create(ChatCreate(user_id=user_id, title=title))
        logger.info("Chat created", chat_id=chat.chat_id, user_id=user_id)
        return chat

    async def get_chat(self, chat_id: str, user_id: str) -> Chat:
        """
        Get chat with ownership verification.

        Args:
            chat_id: Chat identifier
            user_id: User identifier (for ownership check)

        Returns:
            Chat if found and owned by user

        Raises:
            NotFoundError: If chat not found or user doesn't own it
        """
        chat = await self.chat_repo.get(chat_id)

        if not chat:
            raise NotFoundError("Chat not found", chat_id=chat_id)

        if chat.user_id != user_id:
            raise NotFoundError("Chat not found", chat_id=chat_id)  # Don't leak info

        return chat

    async def list_user_chats(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        include_archived: bool = False,
    ) -> tuple[list[Chat], int]:
        """
        List user's chats with pagination.

        Args:
            user_id: User identifier
            page: Page number (1-indexed)
            page_size: Number of chats per page
            include_archived: Whether to include archived chats

        Returns:
            Tuple of (chats list, total count)
        """
        if page < 1:
            raise ValidationError("Page must be >= 1", page=page)

        if page_size < 1 or page_size > 100:
            raise ValidationError("Page size must be 1-100", page_size=page_size)

        chats = await self.chat_repo.list_by_user(
            user_id=user_id,
            limit=page_size,
            skip=(page - 1) * page_size,
            include_archived=include_archived,
        )

        # TODO: Add count_by_user method to chat_repo for total
        total = len(chats)  # Simplified for now

        return chats, total

    async def add_message(
        self,
        chat_id: str,
        user_id: str,
        role: Literal["user", "assistant", "system"],
        content: str,
        source: Literal["user", "llm", "tool"],
        metadata: MessageMetadata | dict[str, Any] | None = None,
        tool_call: Any | None = None,
    ) -> Message:
        """
        Add message to chat and update chat timestamps.

        Args:
            chat_id: Chat identifier
            user_id: User identifier (for ownership check)
            role: Message role (user/assistant/system)
            content: str
            source: Message source (user/llm/tool)
            metadata: Optional message metadata (MessageMetadata or dict)
            tool_call: Optional tool invocation metadata for UI wrapper

        Returns:
            Created message

        Raises:
            NotFoundError: If chat not found or user doesn't own it
        """
        # Verify chat ownership (raises NotFoundError if invalid)
        await self.get_chat(chat_id, user_id)

        # Convert dict metadata to MessageMetadata if needed
        if isinstance(metadata, dict):
            # For dict, wrap it in raw_data if it's analysis data
            if any(
                key in metadata
                for key in ["symbol", "timeframe", "fibonacci_levels", "stochastic_k"]
            ):
                metadata_obj = MessageMetadata(raw_data=metadata)
            else:
                # Try to construct MessageMetadata from dict fields
                metadata_obj = MessageMetadata(**metadata)
        elif metadata is None:
            metadata_obj = MessageMetadata()
        else:
            metadata_obj = metadata

        # Create message
        message = await self.message_repo.create(
            MessageCreate(
                chat_id=chat_id,
                role=role,
                content=content,
                source=source,
                metadata=metadata_obj,
                tool_call=tool_call,
            )
        )

        # Update chat with last message info
        await self.chat_repo.update(
            chat_id,
            ChatUpdate(last_message_preview=content[:200]),
        )
        await self.chat_repo.update_last_message_at(chat_id)

        logger.info(
            "Message added",
            chat_id=chat_id,
            message_id=message.message_id,
            role=role,
            source=source,
        )

        return message

    async def get_chat_messages(
        self, chat_id: str, user_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        """
        Get messages for chat with ownership verification.

        Args:
            chat_id: Chat identifier
            user_id: User identifier (for ownership check)
            limit: Optional limit on number of messages (default: 100)
            offset: Number of messages to skip (default: 0)

        Returns:
            List of messages in chronological order

        Raises:
            NotFoundError: If chat not found or user doesn't own it
        """
        # Verify chat ownership
        await self.get_chat(chat_id, user_id)

        # Get messages with pagination
        messages = await self.message_repo.get_by_chat(
            chat_id, limit=limit or 100, offset=offset
        )

        return messages

    async def update_ui_state(
        self, chat_id: str, user_id: str, ui_state: UIState
    ) -> Chat:
        """
        Update chat UI state.

        Args:
            chat_id: Chat identifier
            user_id: User identifier (for ownership check)
            ui_state: New UI state

        Returns:
            Updated chat

        Raises:
            NotFoundError: If chat not found or user doesn't own it
        """
        # Verify chat ownership
        await self.get_chat(chat_id, user_id)

        # Update UI state
        updated_chat = await self.chat_repo.update_ui_state(chat_id, ui_state)

        if not updated_chat:
            raise NotFoundError("Chat not found", chat_id=chat_id)

        logger.info(
            "UI state updated",
            chat_id=chat_id,
            symbol=ui_state.current_symbol,
            interval=ui_state.current_interval,
        )

        return updated_chat

    async def generate_title_from_llm(
        self, user_message: str, assistant_response: str
    ) -> str:
        """
        Generate chat title using LLM structured output.

        Args:
            user_message: User's first message
            assistant_response: Assistant's first response

        Returns:
            Generated title (max 50 chars)

        Note: This is a simplified implementation.
        In production, you'd call the actual LLM with structured output.
        """
        # TODO: Implement actual LLM call with structured output
        # For now, use a simple heuristic

        # Extract symbols from user message
        import re

        symbols = re.findall(r"\b[A-Z]{1,5}\b", user_message)

        # Detect analysis type
        analysis_types = {
            "fibonacci": ["fibonacci", "fib", "retracement"],
            "stochastic": ["stochastic", "k%", "d%"],
            "macro": ["macro", "sentiment", "vix"],
        }

        detected_type = "Analysis"
        for analysis, keywords in analysis_types.items():
            if any(keyword in user_message.lower() for keyword in keywords):
                detected_type = analysis.capitalize()
                break

        # Build title
        if symbols:
            title = f"{symbols[0]} {detected_type}"
        else:
            title = f"Financial {detected_type}"

        return title[:50]  # Truncate to max length

    async def should_generate_title(self, chat_id: str) -> bool:
        """
        Check if title should be generated for chat.

        Title is generated only once on first user message.

        Args:
            chat_id: Chat identifier

        Returns:
            True if title should be generated
        """
        chat = await self.chat_repo.get(chat_id)

        if not chat:
            return False

        # Generate title if it's still "New Chat" and has messages
        message_count = await self.message_repo.count_by_chat(chat_id)

        return chat.title == "New Chat" and message_count > 0

    async def find_chat_by_symbol(self, user_id: str, symbol: str) -> Chat | None:
        """
        Find active chat for specific symbol.

        Used for symbol-per-chat pattern to prevent duplicate chats.

        Args:
            user_id: User identifier
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Chat if found, None otherwise

        Example:
            >>> chat = await service.find_chat_by_symbol("user_123", "AAPL")
            >>> if chat:
            ...     print(f"Found existing AAPL chat: {chat.chat_id}")
        """
        return await self.chat_repo.find_by_symbol(user_id, symbol)

    async def get_or_create_symbol_chat(self, user_id: str, symbol: str) -> Chat:
        """
        Get existing chat for symbol or create new one.

        Implements symbol-per-chat pattern:
        1. Check if chat exists for symbol
        2. If yes, return existing chat (reuse)
        3. If no, create new chat with symbol in UI state

        Args:
            user_id: User identifier
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Existing or newly created chat

        Example:
            >>> chat = await service.get_or_create_symbol_chat("user_123", "AAPL")
            >>> # Always returns a chat (existing or new)
            >>> print(f"Chat ID: {chat.chat_id}, Symbol: {chat.ui_state.current_symbol}")
        """
        # Try to find existing chat
        existing_chat = await self.find_chat_by_symbol(user_id, symbol)

        if existing_chat:
            logger.info(
                "Reusing existing chat for symbol",
                user_id=user_id,
                symbol=symbol,
                chat_id=existing_chat.chat_id,
            )
            return existing_chat

        # Create new chat with symbol
        new_chat = await self.create_chat(user_id, title=f"{symbol} Analysis")

        # Set symbol in UI state
        ui_state = UIState(current_symbol=symbol)
        updated_chat = await self.update_ui_state(new_chat.chat_id, user_id, ui_state)

        if not updated_chat:
            # Fallback to new_chat if update failed
            logger.warning(
                "Failed to update UI state after chat creation",
                chat_id=new_chat.chat_id,
            )
            return new_chat

        logger.info(
            "Created new chat for symbol",
            user_id=user_id,
            symbol=symbol,
            chat_id=updated_chat.chat_id,
        )

        return updated_chat

    async def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """
        Delete chat and all associated messages.

        Args:
            chat_id: Chat identifier
            user_id: User identifier (for ownership check)

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If chat not found or user doesn't own it
        """
        # Verify chat ownership
        await self.get_chat(chat_id, user_id)

        # Delete all messages first (cascade)
        deleted_messages = await self.message_repo.delete_by_chat(chat_id)

        # Delete chat
        deleted = await self.chat_repo.delete(chat_id)

        if deleted:
            logger.info(
                "Chat deleted",
                chat_id=chat_id,
                user_id=user_id,
                messages_deleted=deleted_messages,
            )

        return deleted
