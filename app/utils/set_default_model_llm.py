from aiohttp import ClientSession
from loguru import logger

from app.services.llm_service import LLMService
from app.services.model_settings_service import ModelSettingsService
from app.db.database import async_session_maker

default_promt = ("Ты помощник по суммирования сообщений из чата телеграма!\n\n"
                         "По истории чата составить саммари следующего вида:\n"
                         "Саммари для чата: \"[Название чата]\"\n"
                         "[Тема1]: небольшое описание о чём тема1 [ссылка]\n\n"
                         "[Тема2]: небольшое описание о чём тема2 [ссылка]\n\n"
                         "и так далее...\n\n\n"
                         "Формат передаваемых сообщений из чата: [время отправки] (tg_id: телеграм айди пользователя) (msg_id: айди сообщения в чате): текст сообщения\n"
                         "Игнорируй спам, флуд и всё, что не относится к репетиторству\n"
                         "Вместо [Тема...] напиши что это за тема\n"
                         "Вместо [ссылка] вставляй html код: <a href=\"https://t.me/c/{{chat_id}}/{{msg_id}}\">[читать]</a>\nВсё форматирование делать только в html\n"
                         "msg_id укзывать тот, с которого началась эта тема\n\n"
                         "Если уместно, можешь использовать смайлики, а также хэштеги")

async def set_default_model_llm(http_session: ClientSession):
    llm_service = LLMService(http_session)
    async with async_session_maker() as session:
        model_settings_service = ModelSettingsService(session)

        current_model = await model_settings_service.get_model()
        if current_model:
            if not current_model.promt:
                await model_settings_service.update_promt(default_promt)
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



