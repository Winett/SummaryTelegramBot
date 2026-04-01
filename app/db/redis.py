from redis.asyncio import Redis
from loguru import logger
from app.core.config import settings


class RedisClient:

    _instance: Redis | None = None

    @classmethod
    async def get_client(cls) -> Redis:
        if cls._instance is None:
            cls._instance = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            try:
                await cls._instance.ping()
                logger.info("✅ Redis подключён")
            except Exception as e:
                logger.error(f"❌ Redis недоступен: {e}")
                raise
        return cls._instance

    @classmethod
    async def close(cls):
        cls._instance: Redis
        if cls._instance and await cls._instance.ping():
            await cls._instance.close()


async def get_redis() -> Redis:
    return await RedisClient.get_client()