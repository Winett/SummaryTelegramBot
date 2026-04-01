from redis.asyncio import Redis

class AdminCache:
    KEY = "admins:telegram_ids"
    TTL = 300  # 5 минут

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_admins_id(self) -> set[int]:
        members = await self.redis.smembers(self.KEY)
        return set(map(int, members)) if members else set()

    async def set_admins_id(self, ids: set[int]):
        await self.redis.delete(self.KEY)
        if ids:
            await self.redis.sadd(self.KEY, *ids)
        await self.redis.expire(self.KEY, self.TTL)

    async def invalidate(self):
        await self.redis.delete(self.KEY)