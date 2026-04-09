from datetime import timezone

from aiogram import Bot, Dispatcher
import aiogram
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from asyncpg.pgproto.pgproto import timedelta

from loguru import logger
from redis.asyncio import Redis

from app.core.config import settings
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.chat import ChatMessageMiddleware
from app.middlewares.service import ServiceMiddleware
from app.middlewares.admin import AdminMiddleware
from app.db.database import async_session_maker
from app.utils.load_admins import load_admins
from app.utils.set_default_model_llm import set_default_model_llm
from app.db.redis import get_redis

from app.handlers import handler_router
from .utils.autogenerate_daily_summary import generate_daily_summary

from app.core.logging import setup_logger

from .webhook import create_prepared_webapp, WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH, WEBHOOK_BASE_URL

_http_client: ClientSession | None = None
_redis: Redis | None = None

def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(DatabaseMiddleware(async_session_maker))
    dp.message.middleware(ServiceMiddleware(_http_client, _redis))
    dp.message.middleware(ChatMessageMiddleware())
    dp.message.middleware(AdminMiddleware())

    dp.my_chat_member.middleware(DatabaseMiddleware(async_session_maker))
    dp.my_chat_member.middleware(ServiceMiddleware(_http_client, _redis))
    dp.my_chat_member.middleware(ChatMessageMiddleware())

    dp.chat_member.middleware(DatabaseMiddleware(async_session_maker))
    dp.chat_member.middleware(ServiceMiddleware(_http_client, _redis))

    dp.callback_query.middleware(DatabaseMiddleware(async_session_maker))
    dp.callback_query.middleware(ServiceMiddleware(_http_client, _redis))
    dp.include_routers(
        handler_router,
    )
    return dp

async def setup_webhook(bot: Bot) -> bool:
    url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != url:
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await bot.set_webhook(url=url, )
        except aiogram.exceptions.TelegramBadRequest as error:
            logger.error(f'Ошибка при установке webhook! {error = }')
            return False
        logger.info(f"Новый webhook установлен! url = {url}")
        return True
    return True


def setup_scheduler(
        bot: Bot,
        http_client: ClientSession,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))


    scheduler.add_job(
        func=generate_daily_summary,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_summary_task",
        name="Генерация ежедневных саммари",
        kwargs={
            "bot": bot,
            "http_client": http_client,
        },
        misfire_grace_time=3600,
        max_instances=1,
        replace_existing=True,
        timezone=timezone(timedelta(hours=3))
    )

    scheduler.start()
    logger.info("🕐 Планировщик запущен: daily_summary в 00:00 МСК")

    return scheduler



async def start_bot():
    logger.debug(f"Настройка логера")
    setup_logger()

    global _http_client
    _http_client = ClientSession()
    global _redis
    _redis = await get_redis()

    bot = Bot(settings.telegram_token)
    dp = create_dispatcher()


    logger.info(f"Запуск бота")
    await bot.delete_webhook()
    setup_scheduler(bot, _http_client)

    # await setup_webhook(bot)
    # logger.info(f"Установил webhooks")
    # app = create_prepared_webapp(bot, dp)
    # runner = web.AppRunner(app)
    # await runner.setup()
    #
    # site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    # await site.start()
    # logger.info(f"Бот запущен на Webhooks")
    # try:
    #     await asyncio.Future()
    # except KeyboardInterrupt:
    #     logger.info('Остановка сервера...')
    # finally:
    #     await runner.cleanup()
    #     await bot.session.close()


    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот авторизован: @{me.username} (id={me.id})")
        await load_admins()
        await set_default_model_llm(_http_client)
    except Exception as e:
        logger.error(f"❌ Не удалось авторизовать бота: {e}")
        return
    try:
        await dp.start_polling(bot)
    finally:
        await _redis.close()
        await _http_client.close()


