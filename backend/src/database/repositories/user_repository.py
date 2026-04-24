"""User repository for user authentication and profile management."""

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from src.core.utils.date_utils import utcnow

from ...models.user import User, UserCreate
from ...services.password import hash_password

logger = structlog.get_logger()


class UserRepository:
    """Repository for user data access operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def create(self, user_create: UserCreate) -> User:
        import uuid

        user_id = f"user_{uuid.uuid4().hex[:12]}"

        if user_create.username:
            username = user_create.username
        elif user_create.email:
            username = f"User_{user_create.email.split('@')[0][:8]}"
        elif user_create.phone_number:
            username = f"User_{user_create.phone_number[-4:]}"
        else:
            username = f"User_{user_id[:8]}"

        password_hash = None
        if user_create.password:
            password_hash = hash_password(user_create.password)

        user = User(
            user_id=user_id,
            email=user_create.email,
            phone_number=user_create.phone_number,
            wechat_openid=user_create.wechat_openid,
            username=username,
            password_hash=password_hash,
            email_verified=False,
            is_admin=False,
            created_at=utcnow(),
            last_login=None,
        )

        user_dict = user.model_dump()
        await self.collection.insert_one(user_dict)

        logger.info("User created", user_id=user_id, email=user_create.email)
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        user_dict = await self.collection.find_one({"user_id": user_id})
        if not user_dict:
            return None
        user_dict.pop("_id", None)
        return User(**user_dict)

    async def get_by_ids(self, user_ids: list[str]) -> dict[str, User]:
        if not user_ids:
            return {}
        cursor = self.collection.find({"user_id": {"$in": user_ids}})
        users_map = {}
        async for user_dict in cursor:
            user_dict.pop("_id", None)
            user = User(**user_dict)
            users_map[user.user_id] = user
        return users_map

    async def get_by_email(self, email: str) -> User | None:
        user_dict = await self.collection.find_one({"email": email})
        if not user_dict:
            return None
        user_dict.pop("_id", None)
        return User(**user_dict)

    async def get_by_phone(self, phone_number: str) -> User | None:
        user_dict = await self.collection.find_one({"phone_number": phone_number})
        if not user_dict:
            return None
        user_dict.pop("_id", None)
        return User(**user_dict)

    async def get_by_username(self, username: str) -> User | None:
        user_dict = await self.collection.find_one({"username": username})
        if not user_dict:
            return None
        user_dict.pop("_id", None)
        return User(**user_dict)

    async def update_last_login(self, user_id: str) -> User | None:
        result = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": {"last_login": utcnow()}},
            return_document=True,
        )
        if not result:
            return None
        result.pop("_id", None)
        return User(**result)
