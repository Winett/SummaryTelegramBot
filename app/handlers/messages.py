from aiogram import Router
from aiogram.client import bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.message_service import MessageService

from .filters import ChatFilter

message_router = Router()

@message_router.message(ChatFilter())
async def message_handler(message: Message, message_service: MessageService):
    if not message.text:
        return
    await message_service.save_message(message)
