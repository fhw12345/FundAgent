"""
Initialize MongoDB indexes for optimal query performance.
Run with: python -m scripts.init_indexes
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import structlog

logger = structlog.get_logger()


async def create_indexes():
    """Create all required indexes for the application."""

    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://mongodb:27017")
    db = client["financial_agent"]

    print("🔧 Initializing MongoDB Indexes\n")

    # ===== Users Collection Indexes =====
    print("📝 Creating indexes for 'users' collection...")
    users = db["users"]

    # Unique index on user_id (primary key)
    await users.create_index("user_id", unique=True, name="idx_user_id")
    print("  ✅ idx_user_id (unique)")

    # Unique partial index on email (only enforces uniqueness for non-null values)
    await users.create_index(
        "email",
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}},
        name="idx_email",
    )
    print("  ✅ idx_email (unique, partial)")

    # Unique partial index on phone_number (only enforces uniqueness for non-null values)
    await users.create_index(
        "phone_number",
        unique=True,
        partialFilterExpression={"phone_number": {"$type": "string"}},
        name="idx_phone_number",
    )
    print("  ✅ idx_phone_number (unique, partial)")

    # Unique partial index on wechat_openid (only enforces uniqueness for non-null values)
    await users.create_index(
        "wechat_openid",
        unique=True,
        partialFilterExpression={"wechat_openid": {"$type": "string"}},
        name="idx_wechat_openid",
    )
    print("  ✅ idx_wechat_openid (unique, partial)")

    # Index on created_at (for analytics)
    await users.create_index("created_at", name="idx_created_at")
    print("  ✅ idx_created_at")

    # ===== Chats Collection Indexes =====
    print("\n💬 Creating indexes for 'chats' collection...")
    chats = db["chats"]

    # Unique index on chat_id (primary key)
    await chats.create_index("chat_id", unique=True, name="idx_chat_id")
    print("  ✅ idx_chat_id (unique)")

    # Compound index on user_id + last_message_at (for listing user's chats sorted)
    await chats.create_index(
        [("user_id", 1), ("last_message_at", -1)],
        name="idx_user_chats",
    )
    print("  ✅ idx_user_chats (user_id + last_message_at)")

    # Compound index on user_id + is_archived (for filtering archived chats)
    await chats.create_index(
        [("user_id", 1), ("is_archived", 1)],
        name="idx_user_archived",
    )
    print("  ✅ idx_user_archived (user_id + is_archived)")

    # Index on updated_at (for sorting)
    await chats.create_index("updated_at", name="idx_updated_at")
    print("  ✅ idx_updated_at")

    # ===== Messages Collection Indexes =====
    print("\n📨 Creating indexes for 'messages' collection...")
    messages = db["messages"]

    # Unique index on message_id (primary key)
    await messages.create_index("message_id", unique=True, name="idx_message_id")
    print("  ✅ idx_message_id (unique)")

    # Compound index on chat_id + timestamp (for fetching chat history chronologically)
    await messages.create_index(
        [("chat_id", 1), ("timestamp", 1)],
        name="idx_chat_messages",
    )
    print("  ✅ idx_chat_messages (chat_id + timestamp)")

    # Compound index on chat_id + source (for filtering by message type)
    await messages.create_index(
        [("chat_id", 1), ("source", 1)],
        name="idx_chat_source",
    )
    print("  ✅ idx_chat_source (chat_id + source)")

    # Compound index on chat_id + source + metadata.symbol (for Fibonacci restoration)
    await messages.create_index(
        [("chat_id", 1), ("source", 1), ("metadata.symbol", 1)],
        name="idx_chat_source_symbol",
    )
    print("  ✅ idx_chat_source_symbol (chat_id + source + metadata.symbol)")

    # Index on timestamp (for global sorting)
    await messages.create_index([("timestamp", -1)], name="idx_timestamp_desc")
    print("  ✅ idx_timestamp_desc")

    print("\n✨ All indexes created successfully!")

    # List all indexes
    print("\n📊 Index Summary:")
    print(f"  Users: {len(await users.index_information())} indexes")
    print(f"  Chats: {len(await chats.index_information())} indexes")
    print(f"  Messages: {len(await messages.index_information())} indexes")

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
