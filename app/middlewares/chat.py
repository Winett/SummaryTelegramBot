from typing import Any, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, Message, CallbackQuery
from loguru import logger

from app.services.chat_service import ChatService
from app.core.config import settings
from app.keyboards.inline import approve_chat_keyboard


class ChatMessageMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Any],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        if isinstance(event, CallbackQuery):
            return await handler(event, data)

        if not isinstance(event, Message):
            return await handler(event, data)

        chat_service: ChatService = data.get('chat_service')
        if chat_service is None:
            raise ValueError("ChatService не найден")

        if event.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            if event.migrate_from_chat_id or event.migrate_to_chat_id:
                logger.info(f"Получил событие по миграции чата")
                await self._handle_migration(event, chat_service)
                return None
            exist_chat = await chat_service.chat_exists(event.chat)

            if not exist_chat:
                await chat_service.get_or_create_chat(event.chat)

                for admin_id in settings.admins:
                    try:
                        await event.bot.send_message(
                            chat_id=admin_id,
                            text=f"🔔 <b>Новый чат!</b>\n\n"
                                 f"📛 Название: {event.chat.title}\n"
                                 f"🆔 ID: <code>{event.chat.id}</code>\n\n"
                                 f"Одобрить?",
                            parse_mode="HTML",
                            reply_markup=approve_chat_keyboard(event.chat.id)
                        )
                        logger.debug(f"Бота добавили в новый чат, уведомляю админов")
                    except Exception as e:
                        logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

                return None

            good_chats = await chat_service.get_good_chats_id()

            if event.chat.id in good_chats:
                return await handler(event, data)
            else:
                logger.debug(f"⏸️ Чат {event.chat.id} не одобрен или неактивен")
                return None

        return await handler(event, data)

    async def _handle_migration(
            self,
            message: Message,
            chat_service: ChatService
    ) -> bool:
        """
        Обрабатывает миграцию чата.
        Returns: True, если это миграция (обработано), False — если обычное сообщение
        """
        if message.migrate_to_chat_id:
            old_id = message.chat.id
            new_id = message.migrate_to_chat_id

            logger.debug(f"🔄 Миграция: {old_id} → {new_id} (сообщение из старого чата)")

            await chat_service.update_chat_telegram_id(old_id, new_id)
            return True

        if message.migrate_from_chat_id:
            old_id = message.migrate_from_chat_id
            new_id = message.chat.id

            logger.debug(f"🔄 Миграция: {old_id} → {new_id} (сообщение из нового чата)")

            exists = await chat_service.chat_exists(message.chat)
            if exists:
                logger.debug(f"✅ Чат {new_id} уже обновлён — пропускаем")
                return True

            await chat_service.update_chat_telegram_id(old_id, new_id)
            return True


        return False

