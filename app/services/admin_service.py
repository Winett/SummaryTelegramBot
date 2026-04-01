from typing import Sequence

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.cache.admin_cache import AdminCache
from app.db.enums import AdminRole
from app.db.models import Admin
from aiogram.types import User

class AdminService:
    def __init__(self, session: AsyncSession, cache: AdminCache):
        self.session = session
        self.cache: AdminCache = cache

    async def get_admins_id(self):
        logger.debug("Получение id администраторов")
        if self.cache:
            cached = await self.cache.get_admins_id()
            if cached:
                logger.debug(f"Взял id администраторов из кэша")
                return cached

        request = select(Admin.telegram_id)
        result = await self.session.execute(request)
        ids = result.scalars().all()
        logger.debug(f"Взял id администраторов из БД")
        if self.cache:
            await self.cache.set_admins_id(set(ids))
            logger.debug(f"Установил id администраторов в кэш")

        return ids

    async def add_admin(self, admin: User) -> bool:
        admin = Admin(
            telegram_id=admin.id,
            username=admin.username,
            full_name=admin.full_name,
        )
        self.session.add(admin)
        try:
            logger.debug(f"Попытка добавить администратора")
            await self.session.commit()
            if self.cache:
                await self.cache.invalidate()
                logger.debug(f"Администратор успешно добавлен, инвалидирую кэш")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Произошла ошибка при добавлении админа, ошибка: {e}")
        return False

    async def add_admin_by_telegram_id(self, telegram_id: int, role: AdminRole = AdminRole.ADMIN) -> bool | None:
        admin = Admin(
            telegram_id=telegram_id,
            role=role,
        )
        self.session.add(admin)
        try:
            logger.debug(f"Попытка добавить администратора по telegram_id")
            await self.session.commit()
            if self.cache:
                await self.cache.invalidate()
                logger.debug(f"Администратор успешно добавлен, инвалидирую кэш")
            return True
        except IntegrityError as e:
            await self.session.rollback()
            if 'uq_admin_telegram_id' in str(e):
                return None
            logger.error(f"Произошла ошибка при добавлении админа, ошибка: {e}")
        return False

    async def remove_admin(self, tg_user_id: int) -> bool:
        request = delete(Admin).where(tg_user_id == Admin.telegram_id)
        try:
            logger.debug(f"Попытка удалить админа")
            await self.session.execute(request)
            await self.session.commit()
            if self.cache:
                await self.cache.invalidate()
                logger.debug(f"Админ успешно удалён, инвлидирую кэш")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Произошла ошибка при удалении админа, ошибка: {e}")
        return False

    async def get_admins(self) -> Sequence[Admin]:
        logger.debug(f"Получаю всех админов")
        request = select(Admin)
        result = await self.session.execute(request)
        return result.scalars().all()

    async def get_admin(self, tg_user_id: int) -> Admin:
        #TODO: добавить кэш для взятия админа по telegram_id
        logger.debug(f"Получаю админа по telegram_id={tg_user_id}")
        request = select(Admin).where(tg_user_id == Admin.telegram_id)
        result = await self.session.execute(request)
        return result.scalars().first()

    async def update_admin(self, user: User) -> bool:
        db_admin = await self.get_admin(user.id)
        if not db_admin:
            return False

        db_admin.username = user.username
        db_admin.full_name = user.full_name

        await self.session.commit()

        return True


