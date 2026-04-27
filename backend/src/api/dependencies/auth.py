"""
Stubbed auth dependencies for single-user FundAgent.

Auth was removed for personal use — all endpoints operate as the local user.
"""

from fastapi import Depends

from ...database.mongodb import MongoDB
from ...database.redis import RedisCache

LOCAL_USER_ID = "local"


def get_mongodb() -> MongoDB:
    from ...main import app
    return app.state.mongodb


def get_redis_cache() -> RedisCache:
    from ...main import app
    return app.state.redis


async def get_current_user_id() -> str:
    return LOCAL_USER_ID


async def get_current_user() -> dict:
    return {"user_id": LOCAL_USER_ID, "username": "local", "is_admin": True}


async def require_admin() -> None:
    return None
