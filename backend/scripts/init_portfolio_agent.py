#!/usr/bin/env python3
"""
Initialize portfolio_agent system user for automated analysis.

This script creates a special "portfolio_agent" user account that:
- Has credit tracking enabled (for monitoring usage)
- Never gets blocked by credit threshold (bypass check)
- Records all LLM usage for cost monitoring
- Starts with generous credit balance (10000 credits)

Run with: python -m scripts.init_portfolio_agent
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for local execution
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from motor.motor_asyncio import AsyncIOMotorClient

from src.models.user import User

logger = structlog.get_logger()


async def init_portfolio_agent_user():
    """Create or update portfolio_agent system user."""

    # Connect to MongoDB
    mongo_url = "mongodb://mongodb:27017"
    client = AsyncIOMotorClient(mongo_url)
    db = client["financial_agent"]
    users_collection = db["users"]

    logger.info("Initializing portfolio_agent system user", mongo_url=mongo_url)

    # Check if portfolio_agent user exists
    existing_user = await users_collection.find_one({"user_id": "portfolio_agent"})

    if existing_user:
        logger.info(
            "Portfolio agent user already exists",
            user_id="portfolio_agent",
            current_credits=existing_user.get("credits", 0),
        )
        print("✅ Portfolio agent user already exists")
        print(f"   Current credits: {existing_user.get('credits', 0)}")
        print(f"   Total tokens used: {existing_user.get('total_tokens_used', 0)}")
        print(f"   Total credits spent: {existing_user.get('total_credits_spent', 0)}")
        return

    # Create new portfolio_agent user
    portfolio_agent = User(
        user_id="portfolio_agent",
        username="portfolio_agent",
        email=None,  # System account
        phone_number=None,
        wechat_openid=None,
        password_hash=None,  # No password - not for login
        email_verified=False,
        is_admin=False,
        credits=10000.0,  # Generous initial balance for monitoring
        total_tokens_used=0,
        total_credits_spent=0.0,
        feedbackVotes=[],
    )

    # Insert to database
    user_dict = portfolio_agent.model_dump(by_alias=False, exclude={"id"})
    result = await users_collection.insert_one(user_dict)

    logger.info(
        "Portfolio agent user created",
        user_id="portfolio_agent",
        initial_credits=10000.0,
        inserted_id=str(result.inserted_id),
    )

    print("\n✅ Portfolio agent user created successfully!")
    print("   User ID: portfolio_agent")
    print("   Initial credits: 10000.0")
    print("   Purpose: Automated portfolio analysis with credit tracking")
    print("   Blocking: Disabled (credit check bypassed)\n")

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(init_portfolio_agent_user())
