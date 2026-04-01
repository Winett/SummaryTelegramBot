from app.db.models import User
from redis.asyncio import Redis

class UserCache:

    def __init__(self, redis: Redis):
        self.redis = redis

    def get_user(self, telegram_user_id: int) -> User:
        ...

