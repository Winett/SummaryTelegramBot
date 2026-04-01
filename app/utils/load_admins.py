from loguru import logger

from app.core.config import settings
from app.db.enums import AdminRole
from app.services.admin_service import AdminService
from app.db.database import async_session_maker
from app.cache.admin_cache import AdminCache
from app.db.redis import get_redis

async def load_admins():
    admin_service = AdminService(async_session_maker(), AdminCache(await get_redis()))
    for admin_id in settings.admins:
        res = await admin_service.add_admin_by_telegram_id(admin_id, role=AdminRole.OWNER)
        if res:
            logger.info(f"Админ с id {admin_id} успешно добавлен в БД")
        elif res is False:
            logger.warning(f"Админа с id {admin_id} не удалось добавить")
        else: # if None
            logger.info(f"Админ с id {admin_id} уже записан в администраторах")