from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatMemberStatus
from loguru import logger

from app.services.chat_service import ChatService

chat_events_router = Router()

@chat_events_router.my_chat_member()
async def on_chat_member_invite(event: ChatMemberUpdated, chat_service: ChatService):
    if event.new_chat_member.status == ChatMemberStatus.MEMBER:
        ...

    elif event.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        await chat_service.deactivate_chat(event.chat)
        await chat_service.disapprove_chat(event.chat)
        logger.info(f"Бот удалён из чата {event.chat.id}")


    elif event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        logger.info(f"Бот стал администратором")

    elif event.new_chat_member.status == ChatMemberStatus.CREATOR:
        logger.info(f"Бот стал создателем")

