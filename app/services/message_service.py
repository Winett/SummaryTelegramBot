from datetime import datetime
from typing import Sequence

from aiogram.types import Message, User, Chat
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Message as MessageModel, Chat as ChatModel, User as UserModel
from .chat_service import ChatService
from .user_service import UserService
from loguru import logger


class MessageService:
    def __init__(self, session: AsyncSession, chat_service: ChatService):
        self.session: AsyncSession = session
        self.chat_service: ChatService = chat_service

    async def save_message(self, message: Message):
        if not message.from_user:
            logger.warning(f"Получено сообщение без поля from_user; Возможно оно отправлено от лица канала")
            return False
        try:
            chat = await self._get_or_create_chat(message.chat)
            user = await self._get_or_create_user(message.from_user)

            msg = MessageModel(
                chat_id=chat.id,
                user_id=user.id,
                telegram_message_id=message.message_id,
                text=message.text,
                sent_at=message.date,
            )
            self.session.add(msg)
            await self.session.commit()
            return True

        except IntegrityError as e:
            await self.session.rollback()

            if "uq_message_telegram" in str(e):
                return True  # Такое поле уже существует
            return False
        except SQLAlchemyError as e:

            await self.session.rollback()
            logger.error(f"Ошибка БД при сохранении сообщения; error={ e = }")
            return False

    async def _get_or_create_chat(self, tg_chat: Chat) -> ChatModel:

        return await self.chat_service.get_or_create_chat(tg_chat)

    async def _get_or_create_user(self, tg_user: User) -> UserModel:

        return await UserService(self.session).get_or_create_user(tg_user)

    async def get_messages(self, chat_id: int, date_start: datetime, date_end: datetime) -> Sequence[MessageModel]:
        request = select(MessageModel).where(chat_id == MessageModel.chat_id, MessageModel.created_at >= date_start, MessageModel.created_at <= date_end)\
        .options(selectinload(MessageModel.user))
        result = await self.session.execute(request)
        messages = result.scalars().all()
        return messages

    async def delete_messages(self, chat_id: int, date_start: datetime, date_end: datetime) -> bool:
        request = delete(MessageModel).where(chat_id == MessageModel.chat_id, MessageModel.created_at >= date_start, MessageModel.created_at <= date_end)
        try:
            result = await self.session.execute(request)
            await self.session.commit()
            return True
        except IntegrityError as e:
            await self.session.rollback()
        return False




