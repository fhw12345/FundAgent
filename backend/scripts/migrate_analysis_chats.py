#!/usr/bin/env python3
"""
Migrate user analysis chats to portfolio_agent.

All chats with titles ending in "Analysis" should belong to portfolio_agent,
not individual users, so they appear ONLY in the portfolio analysis sidebar.
"""

import os
import sys
from pymongo import MongoClient

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.config import get_settings

def migrate_analysis_chats():
    """Migrate all user analysis chats to portfolio_agent user_id."""
    settings = get_settings()
    client = MongoClient(settings.mongodb_url)
    db = client.get_database()
    chats_collection = db.chats

    print("=" * 70)
    print("MIGRATING ANALYSIS CHATS TO PORTFOLIO_AGENT")
    print("=" * 70)

    # Find all chats with "Analysis" in title that are NOT already portfolio_agent
    query = {
        "title": {"$regex": "Analysis$"},  # Ends with "Analysis"
        "user_id": {"$ne": "portfolio_agent"}  # Not already portfolio_agent
    }

    chats_to_migrate = list(chats_collection.find(query))

    if not chats_to_migrate:
        print("\n✅ No chats need migration. All analysis chats are already portfolio_agent.")
        return

    print(f"\nFound {len(chats_to_migrate)} analysis chats to migrate:\n")

    for chat in chats_to_migrate:
        print(f"  • {chat['title']}")
        print(f"    Current user_id: {chat['user_id']}")
        print(f"    Chat ID: {chat['chat_id']}")
        print()

    # Confirm migration
    response = input(f"\nMigrate {len(chats_to_migrate)} chats to portfolio_agent? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("❌ Migration cancelled.")
        return

    # Perform migration
    result = chats_collection.update_many(
        query,
        {"$set": {"user_id": "portfolio_agent"}}
    )

    print(f"\n✅ Migration complete!")
    print(f"   Updated {result.modified_count} chats")

    # Verify migration
    remaining = chats_collection.count_documents(query)
    print(f"   Remaining non-portfolio analysis chats: {remaining}")

    if remaining == 0:
        print("\n🎉 All analysis chats are now under portfolio_agent!")
    else:
        print(f"\n⚠️  Warning: {remaining} analysis chats still not migrated")

    # Show final counts
    print("\n" + "=" * 70)
    print("FINAL CHAT COUNTS")
    print("=" * 70)

    portfolio_count = chats_collection.count_documents({"user_id": "portfolio_agent"})
    user_count = chats_collection.count_documents({
        "user_id": {"$ne": "portfolio_agent"}
    })

    print(f"Portfolio agent chats: {portfolio_count}")
    print(f"User chats (non-analysis): {user_count}")
    print()

if __name__ == "__main__":
    migrate_analysis_chats()
