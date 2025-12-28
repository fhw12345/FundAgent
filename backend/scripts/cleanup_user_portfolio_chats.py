#!/usr/bin/env python3
"""
Clean up portfolio analysis messages that leaked into user chats.

This script deletes chats from user accounts that contain portfolio analysis
messages. These are duplicates that should only exist under portfolio_agent.
"""

import asyncio
import sys
from pathlib import Path

# Add backend src to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir / "src"))


from motor.motor_asyncio import AsyncIOMotorClient


async def cleanup_user_portfolio_chats(dry_run: bool = True):
    """
    Delete portfolio analysis chats from user accounts.

    Args:
        dry_run: If True, only show what would be deleted without actually deleting
    """
    client = AsyncIOMotorClient("mongodb://mongodb:27017")
    db = client["financial_agent"]
    chats_collection = db["chats"]
    messages_collection = db["messages"]

    print("=" * 80)
    print("CLEANUP: Portfolio Messages in User Chats")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will delete)'}")
    print("=" * 80)
    print()

    # Find all user chats (not portfolio_agent)
    user_chats = await chats_collection.find(
        {"user_id": {"$ne": "portfolio_agent"}}
    ).to_list(length=None)

    chats_to_delete = []

    for chat in user_chats:
        chat_id = chat.get("chat_id")
        user_id = chat.get("user_id")
        title = chat.get("title", "Untitled")

        # Get messages for this chat
        messages = await messages_collection.find({"chat_id": chat_id}).to_list(
            length=None
        )

        # Check if this chat contains portfolio analysis
        is_portfolio_chat = False
        if messages:
            for msg in messages:
                content = msg.get("content", "")
                content_lower = content.lower()
                # Portfolio analysis indicators
                if (
                    any(
                        indicator in content_lower
                        for indicator in [
                            "fibonacci analysis",
                            "stochastic analysis",
                            "watchlist",
                            "portfolio analysis",
                            "trend: uptrend",
                            "trend: downtrend",
                            "support level",
                            "resistance level",
                            "key fibonacci levels",
                            "rsi",
                            "portfolio agent analysis",  # New format
                            "decision: buy",
                            "decision: sell",
                            "decision: hold",
                            "position_size:",
                            "analysis_id:",
                        ]
                    )
                    or "## 📈 Portfolio Agent Analysis" in content
                ):  # Check exact header
                    is_portfolio_chat = True
                    break

        if is_portfolio_chat:
            chats_to_delete.append(
                {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "title": title,
                    "message_count": len(messages),
                    "created_at": chat.get("created_at"),
                }
            )

    if not chats_to_delete:
        print("✅ No portfolio chats found in user accounts - database is clean!")
        return

    print(f"Found {len(chats_to_delete)} chats to delete:\n")

    total_messages = 0
    for idx, chat_info in enumerate(chats_to_delete, 1):
        total_messages += chat_info["message_count"]
        print(f"{idx}. {chat_info['title']}")
        print(f"   Chat ID: {chat_info['chat_id']}")
        print(f"   User: {chat_info['user_id']}")
        print(f"   Messages: {chat_info['message_count']}")
        print(f"   Created: {chat_info['created_at']}")
        print()

    print(f"Total: {len(chats_to_delete)} chats, {total_messages} messages")
    print()

    if dry_run:
        print("=" * 80)
        print("DRY RUN - No changes made")
        print("=" * 80)
        print("\nTo actually delete these chats, run:")
        print(
            "  docker compose exec backend python scripts/cleanup_user_portfolio_chats.py --execute"
        )
        return

    # Actually delete
    print("=" * 80)
    print("EXECUTING DELETION")
    print("=" * 80)
    print()

    deleted_chats = 0
    deleted_messages = 0

    for chat_info in chats_to_delete:
        chat_id = chat_info["chat_id"]

        # Delete messages first
        msg_result = await messages_collection.delete_many({"chat_id": chat_id})
        deleted_messages += msg_result.deleted_count

        # Delete chat
        chat_result = await chats_collection.delete_one({"chat_id": chat_id})
        deleted_chats += chat_result.deleted_count

        print(f"✅ Deleted: {chat_info['title']} ({msg_result.deleted_count} messages)")

    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print(f"Deleted: {deleted_chats} chats, {deleted_messages} messages")
    print()

    # Verify cleanup
    remaining = await chats_collection.count_documents(
        {"user_id": {"$ne": "portfolio_agent"}}
    )
    print(f"Remaining user chats: {remaining}")

    portfolio_chats = await chats_collection.count_documents(
        {"user_id": "portfolio_agent"}
    )
    print(f"Portfolio agent chats: {portfolio_chats}")


async def main():
    # Check if --execute flag is passed
    execute = "--execute" in sys.argv

    if execute:
        print("\n⚠️  WARNING: This will DELETE chats and messages from the database!")
        print("⚠️  Make sure you have a backup if needed.")
        print()
        response = input("Type 'DELETE' to confirm: ")
        if response != "DELETE":
            print("Aborted.")
            return
        print()

    await cleanup_user_portfolio_chats(dry_run=not execute)


if __name__ == "__main__":
    asyncio.run(main())
