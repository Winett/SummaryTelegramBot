from aiohttp import ClientSession
from app.services.llm_client import LLMClient

from app.core.config import settings


class LLMService:

    def __init__(self, http_session: ClientSession):
        self.http_session = http_session
        self.llm_client = LLMClient(self.http_session, api_key=settings.openrouter_api_key)

    async def get_models(self):
        return await self.llm_client.get_models()

    async def get_balance(self):
        return await self.llm_client.get_balance()

