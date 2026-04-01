from aiogram import BaseMiddleware
from redis.asyncio import Redis

from app.core.config import settings
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.chat_service import ChatService
from app.services.summary_service import SummaryService
from app.services.admin_service import AdminService
from app.cache.chat_cache import RedisChatCache
from app.cache.admin_cache import AdminCache
from app.services.model_settings_service import ModelSettingsService
from app.services.llm_service import LLMService
from app.services.llm_client import LLMClient


from aiohttp import ClientSession


class ServiceMiddleware(BaseMiddleware):
    def __init__(self, http_client: ClientSession = None, redis: Redis = None):
        if http_client is None:
            raise ValueError("Http client не передан")
        if not redis:
            raise ValueError("Redis не передан")
        self.http_client: ClientSession = http_client
        self.redis: Redis = redis

    async def __call__(self, handler, event, data):
        session = data.get('session')

        if not session:
            raise ValueError
        chat_service = ChatService(session, redis_cache=RedisChatCache(self.redis))
        model_setting_service = ModelSettingsService(session)
        model = await model_setting_service.get_model()

        data['user_service'] = UserService(session)
        data['chat_service'] = chat_service
        data['message_service'] = MessageService(session, chat_service)
        data['model_settings_service'] = model_setting_service
        data['summary_service'] = SummaryService(session, LLMClient(self.http_client, api_key=settings.openrouter_api_key, model_id=model.llm_id, max_context_tokens=model.context_length))
        data['admin_service'] = AdminService(session, cache=AdminCache(self.redis))
        data['llm_service'] = LLMService(self.http_client)

        return await handler(event, data)