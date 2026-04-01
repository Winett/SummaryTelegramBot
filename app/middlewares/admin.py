from typing import Any, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, Message

from app.core.config import settings
from app.services.admin_service import AdminService


class AdminMiddleware(BaseMiddleware):

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Any],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        admin_service: AdminService = data.get('admin_service')
        admins_id = await admin_service.get_admins_id()

        if isinstance(event, Message) and event.chat.type == ChatType.PRIVATE and (event.from_user.id not in admins_id):
            event: Message
            return await event.answer(
                "⛔ Вы не являетесь администратором!\nДоступ запрещён!")
        await admin_service.update_admin(event.from_user)
        return await handler(event, data)

