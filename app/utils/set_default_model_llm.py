from aiohttp import ClientSession
from loguru import logger

from app.services.llm_service import LLMService
from app.services.model_settings_service import ModelSettingsService
from app.db.database import async_session_maker

async def set_default_model_llm(http_session: ClientSession):
    llm_service = LLMService(http_session)
    async with async_session_maker() as session:
        model_settings_service = ModelSettingsService(session)

        current_model = await model_settings_service.get_model()
        if current_model:
            logger.info(f"Модель по умолчанию уже установлена: '{current_model.name}'")
            return

        models = await llm_service.get_models()
        model_to_use = "qwen/qwen3.5-flash-02-23"
        model = None
        for model in models:
            if model_to_use == model["llm_id"]:
                break
        else:
            model = models[0]
        try:
            await model_settings_service.set_model_if_not_exists(**model)
            logger.info(f"Модель по умолчанию успешно установлена: '{model.get('name')}'")
        except Exception as e:
            logger.error(f"Ошибка установки модели по умолчанию: {e}")

