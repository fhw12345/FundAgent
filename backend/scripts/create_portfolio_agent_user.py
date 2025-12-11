"""
Create portfolio_agent system user.

This script creates a special system user for portfolio analysis:
- user_id: "portfolio_agent"
- username: "portfolio_agent"
- email: "portfolio_agent@system.internal"
- role: "system"
- credits: 1,000,000 (high limit for autonomous analysis)
- is_active: True
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import get_settings


async def create_portfolio_agent_user():
    """Create portfolio_agent system user."""
    settings = get_settings()

    # Connect to MongoDB directly
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.get_database("financial_agent")
    users_collection = db.get_collection("users")

    # Check if portfolio_agent already exists
    existing_user = await users_collection.find_one({"username": "portfolio_agent"})
    if existing_user:
        print("✅ Portfolio agent user already exists:")
        print(f"   user_id: {existing_user['user_id']}")
        print(f"   username: {existing_user['username']}")
        print(f"   email: {existing_user.get('email')}")
        print(f"   credits: {existing_user.get('credits')}")
        print(f"   is_admin: {existing_user.get('is_admin')}")
        return existing_user

    # Insert directly (bypass normal user creation to set custom user_id)
    user_dict = {
        "user_id": "portfolio_agent",
        "username": "portfolio_agent",
        "email": "portfolio_agent@system.internal",
        "password_hash": "",  # No password - system user, no login
        "email_verified": True,
        "is_admin": False,  # Not admin, just system user
        "credits": 1_000_000.0,  # High credit limit for autonomous analysis
        "total_tokens_used": 0,
        "total_credits_spent": 0.0,
        "feedbackVotes": [],
        "created_at": datetime.utcnow(),
        "last_login": None,
    }

    result = await users_collection.insert_one(user_dict)

    print("✅ Created portfolio_agent system user:")
    print("   user_id: portfolio_agent")
    print("   username: portfolio_agent")
    print("   email: portfolio_agent@system.internal")
    print("   credits: 1,000,000")
    print("   is_admin: False")
    print(f"   _id: {result.inserted_id}")

    # Verify
    user = await users_collection.find_one({"username": "portfolio_agent"})
    return user


if __name__ == "__main__":
    asyncio.run(create_portfolio_agent_user())
