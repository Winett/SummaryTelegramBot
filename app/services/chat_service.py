from datetime import datetime
from typing import Optional, List
from aiogram.types import Chat as TgChat
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from loguru import logger

from app.cache.chat_cache import RedisChatCache
from app.db.models import Chat as ChatModel, Message as MessageModel
from app.shemas.chat import ChatSchema



class ChatService:


    def __init__(self, session, redis_cache: RedisChatCache | None = None):
        self.session = session
        self.cache = redis_cache


    async def get_or_create_chat(self, tg_chat: TgChat) -> ChatModel:
        if self.cache:
            cached = await self.cache.get_chat(tg_chat.id)
            if cached:
                logger.debug(f"Взял данные чата из кэша")
                return ChatModel(**cached.model_dump())

        result = await self.session.execute(
            select(ChatModel).where(tg_chat.id == ChatModel.telegram_id)
        )
        chat = result.scalar_one_or_none()

        if not chat:
            chat = ChatModel(
                telegram_id=tg_chat.id,
                title=tg_chat.title or f"Chat {tg_chat.id}",
                language="ru",
                is_active=True,
                is_approved=False
            )

            self.session.add(chat)
            await self.session.commit()
            await self.session.refresh(chat)

            logger.info(f"✅ Создан новый чат: {chat.title} (tg_id={tg_chat.id})")
        else:
            if chat.title != tg_chat.title:
                chat.title = tg_chat.title or chat.title
                await self.session.commit()

        if chat and self.cache:
            await self.cache.set_chat(tg_chat.id, ChatSchema.model_validate(chat))
            logger.debug(f"Установил данные чата в кэша")

        return chat

    async def update_chat_telegram_id(self, from_telegram_id: int, to_telegram_id: int):
        stmt = select(ChatModel).where(from_telegram_id == ChatModel.telegram_id)
        result = await self.session.execute(stmt)
        chat = result.scalar_one_or_none()
        if not chat:
            return False
        chat.telegram_id = to_telegram_id
        await self.session.commit()
        return True

    async def get_all_chats(self) -> List[ChatModel]:
        result = await self.session.execute(select(ChatModel))
        return result.scalars().all()

    async def get_chats_telegram_id_and_title(self) -> list[tuple[int, str]]:
        result = await self.session.execute(
            select(ChatModel.telegram_id, ChatModel.title)
        )
        return result.all()

    async def get_chat_by_telegram_id(self, telegram_id: int, with_admins: bool = False) -> Optional[ChatModel]:
        """Получить чат по Telegram ID"""
        if with_admins:
            result = await self.session.execute(
                select(ChatModel)
                .where(telegram_id == ChatModel.telegram_id)
                .options(selectinload(ChatModel.admins))
            )
            return result.scalar_one_or_none()

        if self.cache:
            cached = await self.cache.get_chat(telegram_id)
            if cached:
                logger.debug(f"✅ Чат {telegram_id} из кэша (без админов)")
                return ChatModel(**cached.model_dump())

        result = await self.session.execute(
            select(ChatModel).where(telegram_id == ChatModel.telegram_id)
        )
        chat = result.scalar_one_or_none()

        if chat and self.cache:
            await self.cache.set_chat(telegram_id, ChatSchema.model_validate(chat))
            logger.debug(f"Установил данные чата в кэша")

        return chat

    async def get_chat_by_id(self, chat_id: int) -> Optional[ChatModel]:
        """Получить чат по локальному ID в БД"""
        result = await self.session.execute(
            select(ChatModel).where(ChatModel.id == chat_id)
        )
        return result.scalar_one_or_none()


    async def activate_chat(self, tg_chat: TgChat) -> bool:
        """Активировать чат (разрешить сохранение сообщений)"""
        return await self._update_chat_status(tg_chat.id, is_active=True)

    async def active_chat_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, is_active=True)

    async def deactivate_chat(self, tg_chat: TgChat) -> bool:
        """Деактивировать чат (остановить сохранение сообщений)"""
        return await self._update_chat_status(tg_chat.id, is_active=False)

    async def deactivate_chat_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, is_active=False)

    async def approve_chat(self, tg_chat: TgChat) -> bool:
        """Одобрить чат (подтверждение от админа бота)"""
        return await self._update_chat_status(tg_chat.id, is_approved=True)

    async def approve_chat_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, is_approved=True)

    async def disapprove_chat(self, tg_chat: TgChat) -> bool:
        """Отклонить чат"""
        return await self._update_chat_status(tg_chat.id, is_approved=False)

    async def disapprove_chat_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, is_approved=False)

    async def active_chat_to_send_summary(self, tg_chat: TgChat) -> bool:
        return await self._update_chat_status(tg_chat.id, to_send_summary=True)
    async def active_chat_to_send_summary_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, to_send_summary=True)

    async def deactive_chat_to_send_summary(self, tg_chat: TgChat) -> bool:
        return await self._update_chat_status(tg_chat.id, to_send_summary=False)
    async def deactive_chat_to_send_summary_by_telegram_id(self, telegram_id: int) -> bool:
        return await self._update_chat_status(telegram_id, to_send_summary=False)
    # @catch_SQLAlchemyError
    async def _update_chat_status(self, telegram_id: int, **kwargs) -> bool:
        await self.cache.delete_chat(telegram_id)
        chat = await self.get_chat_by_telegram_id(telegram_id)
        if not chat:
            return False

        for key, value in kwargs.items():
            if hasattr(chat, key):
                setattr(chat, key, value)

        await self.session.commit()

        if self.cache:
            await self.cache.set_chat(chat.id, ChatSchema.model_validate(chat))
            await self.cache.delete_good_chat_ids()
            await self.cache.delete_chat(telegram_id)
            logger.debug(f"Установил данные чата в кэша")

        return True

    async def delete_chat(self, tg_chat: TgChat) -> bool:
        chat = await self.get_chat_by_telegram_id(tg_chat.id)
        if not chat:
            return False

        await self.session.delete(chat)
        await self.session.commit()
        logger.info(f"🗑️ Чат удалён: {tg_chat.title} (tg_id={tg_chat.id})")
        return True

    async def get_good_chats_id(self):
        if self.cache:
            cached = await self.cache.get_good_chat_ids()
            logger.debug(f"Взял данные id чатаов из кэша")
            if cached:
                return cached
        stmt = select(ChatModel.telegram_id).where(True == ChatModel.is_approved, True == ChatModel.is_active)
        result = await self.session.execute(stmt)
        ids_set =  set(result.scalars().all())
        if self.cache and ids_set:
            await self.cache.set_good_chat_ids(ids_set)
            logger.debug(f"Установил данные id чатов в кэш")
        return ids_set

    async def chat_exists(self, tg_chat: TgChat) -> bool:
        #TODO: добавить кэш, просматривать, есть ли чат в кэше
        stmt = select(ChatModel).where(tg_chat.id == ChatModel.telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_chats_to_send_summary(self):
        smtm = select(ChatModel).where(True == ChatModel.to_send_summary)
        result = await self.session.execute(smtm)
        return result.scalars().all()

    async def get_chats_id_to_get_summary(self, date_start: datetime, date_end: datetime) -> list[ChatModel]:
        smtm = (
            select(ChatModel)
            .join(MessageModel, ChatModel.id == MessageModel.chat_id)
            .where(MessageModel.sent_at >= date_start, MessageModel.sent_at <= date_end)
            .distinct()
        )
        result = await self.session.execute(smtm)
        return result.scalars().all()