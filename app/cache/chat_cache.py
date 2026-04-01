import json
from redis.asyncio import Redis
from loguru import logger

from app.shemas.chat import ChatSchema


class RedisChatCache:

    KEY_PREFIX = "chat:"
    KEY_PREFIX_CHAT = f"{KEY_PREFIX}tg_id:"
    KEY_PREFIX_GOOD_CHATS = f"{KEY_PREFIX}good_chats"
    TTL_SECONDS = 300 # 5 минут
    TTL_GOOD_CHATS = 900 # 15 минут

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_chat(self, telegram_id: int) -> ChatSchema | None:
        """Получить чат из кэша"""
        key = f"{self.KEY_PREFIX_CHAT}{telegram_id}"
        try:
            data = await self.redis.get(key)
            if data:
                chat_data = json.loads(data)
                return ChatSchema(**chat_data)
        except Exception as e:
            logger.error(f"❌ Ошибка чтения кэша чата: {e}")
        return None

    async def set_chat(self, telegram_id: int, chat_data: ChatSchema, ttl: int = None):
        """Сохранить чат в кэш"""
        logger.info("Получение из кэша чата")
        key = f"{self.KEY_PREFIX_CHAT}{telegram_id}"
        try:
            await self.redis.setex(
                key,
                ttl or self.TTL_SECONDS,
                chat_data.model_dump_json(),
            )
        except Exception as e:
            logger.error(f"❌ Ошибка записи кэша чата: {e}")

    async def delete_chat(self, telegram_id: int):
        """Удалить чат из кэша (при обновлении)"""
        logger.info("Удаление из кэша чата")
        key = f"{self.KEY_PREFIX_CHAT}{telegram_id}"
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"❌ Ошибка удаления кэша чата: {e}")

    async def clear_all(self):
        """Очистить весь кэш чатов (для отладки)"""
        try:
            keys = await self.redis.keys(f"{self.KEY_PREFIX}*")
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"🗑️ Очищено {len(keys)} ключей кэша чатов")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")

    async def get_good_chat_ids(self) -> set[int]:
        try:
            members = await self.redis.smembers(self.KEY_PREFIX_GOOD_CHATS)
            return set(map(int, members)) if members else set()
        except Exception as e:
            logger.error(f"❌ Ошибка чтения кэша хороших чатов: {e}")
            return set()


    async def set_good_chat_ids(self, ids: set[int]):
        """Полная перезапись списка (при инициализации или массовом изменении)"""
        try:
            await self.redis.delete(self.KEY_PREFIX_GOOD_CHATS)
            if ids:
                await self.redis.sadd(self.KEY_PREFIX_GOOD_CHATS, *ids)
                await self.redis.expire(self.KEY_PREFIX_GOOD_CHATS, self.TTL_GOOD_CHATS)
        except Exception as e:
            logger.error(f"❌ Ошибка записи кэша хороших чатов: {e}")

    async def delete_good_chat_ids(self):
        try:
            await self.redis.delete(self.KEY_PREFIX_GOOD_CHATS)
        except Exception as e:
            logger.error(f"❌ Ошибка удаления 'хороших' чатов")