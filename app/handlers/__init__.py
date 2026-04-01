from aiogram import Router

from .messages import message_router
from .commands import commands_router
from .chat_events import chat_events_router
from .callback_query import callback_query_router
from .admin import admin_router

handler_router = Router()


handler_router.include_routers(
    message_router,
    commands_router,
    chat_events_router,
    callback_query_router,
    admin_router,
)