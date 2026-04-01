from typing import Any, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from loguru import logger


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Any],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        try:
            async with self.session_pool() as session:
                data['session'] = session
                result = await handler(event, data)
                return result
        except Exception as e:
            logger.error(f"❌ Middleware error: {e}")
            raise