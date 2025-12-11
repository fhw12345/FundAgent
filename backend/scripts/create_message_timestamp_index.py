#!/usr/bin/env python3
"""
Create MongoDB index for message timestamps.

Optimizes date-range queries on messages collection.

Usage:
    python backend/scripts/create_message_timestamp_index.py
"""

import asyncio
import os
import sys

# Add backend/src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.config import get_settings
from src.database.mongodb import MongoDB


async def create_message_timestamp_index():
    """Create compound index on messages.timestamp and messages.chat_id."""
    settings = get_settings()
    mongodb = MongoDB(settings.mongodb_url, settings.mongodb_db_name)
    await mongodb.connect()

    try:
        messages_collection = mongodb.get_collection("messages")

        # Create compound index: timestamp (desc) + chat_id (asc)
        # Optimizes queries like: find({chat_id: X, timestamp: {$gte: Y, $lt: Z}})
        index_name = await messages_collection.create_index(
            [("timestamp", -1), ("chat_id", 1)],  # -1 = descending
            name="timestamp_chat_id_idx",
        )

        print(f"✅ Index created: {index_name}")
        print("   Collection: messages")
        print("   Fields: timestamp (desc), chat_id (asc)")
        print("   Optimizes: Date-range queries on chat messages")

        # Verify index exists
        indexes = await messages_collection.list_indexes().to_list(length=None)
        print("\n📋 All indexes on 'messages' collection:")
        for idx in indexes:
            print(f"   - {idx['name']}: {idx['key']}")

    finally:
        await mongodb.disconnect()


if __name__ == "__main__":
    asyncio.run(create_message_timestamp_index())
