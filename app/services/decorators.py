from functools import wraps
from typing import Callable

from loguru import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def catch_IntegrityError(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(f"Ошибка IntegrityError при вызове функции {func.__name__}(self, args={args}, kwargs={kwargs}): {e}")
            return None
    return wrapper

def catch_SQLAlchemyError(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Ошибка БД SQLAlchemyError при вызове функции {func.__name__}(self, args={args}, kwargs={kwargs}): {e}")
            return None
    return wrapper
