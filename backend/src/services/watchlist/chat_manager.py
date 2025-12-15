"""
Chat management utilities for watchlist analysis.

Handles symbol-specific chat creation and retrieval.
"""

import structlog

from ...database.repositories.chat_repository import ChatRepository
from ...models.chat import ChatCreate

logger = structlog.get_logger()


class ChatManager:
    """Manages symbol-specific chats for watchlist analysis."""

    def __init__(self, chat_repo: ChatRepository):
        """
        Initialize chat manager.

        Args:
            chat_repo: Repository for chat operations
        """
        self.chat_repo = chat_repo

    async def get_symbol_chat_id(self, symbol: str) -> str:
        """
        Get or create a dedicated chat for this symbol.

        Each symbol gets its own chat (e.g., "XIACY Analysis") where all
        analyses for that symbol are stored as messages.

        Args:
            symbol: Stock symbol (e.g., "XIACY", "MSFT")

        Returns:
            Chat ID for this symbol
        """
        # Try to find existing chat for this symbol
        # Search by title pattern: "{symbol} Analysis"
        chats = await self.chat_repo.list_by_user("portfolio_agent")
        for chat in chats:
            if chat.title and chat.title.startswith(f"{symbol} "):
                logger.info(
                    "Found existing chat for symbol",
                    symbol=symbol,
                    chat_id=chat.chat_id,
                )
                return chat.chat_id

        # Create new chat for this symbol
        chat_create = ChatCreate(title=f"{symbol} Analysis", user_id="portfolio_agent")
        chat = await self.chat_repo.create(chat_create)
        logger.info("Created new chat for symbol", symbol=symbol, chat_id=chat.chat_id)
        return chat.chat_id
