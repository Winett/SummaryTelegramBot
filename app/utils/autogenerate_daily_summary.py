# from aiogram import Bot
# from aiogram.enums import ParseMode
# from aiohttp import ClientSession
#
# from app.db.database import async_session_maker
# from app.services.chat_service import ChatService
# from app.services.summary_service import SummaryService
# from app.services.model_settings_service import ModelSettingsService
# from app.services.llm_client import LLMClient
# from app.core.config import settings
# import asyncio
#
# from datetime import datetime, timedelta, timezone
#
# async def generate_daily_summary(bot: Bot, http_client: ClientSession):
#     async with async_session_maker() as session:
#         chat_service = ChatService(session)
#         model_settings = await ModelSettingsService(session).get_model()
#         summary_service = SummaryService(session, LLMClient(http_client, api_key=settings.openrouter_api_key, model_id=model_settings.name, max_context_tokens=model_settings.context_length))
#
#         chats_to_send_summary = await chat_service.get_chats_to_send_summary()
#
#         now = datetime.now(timezone(timedelta(hours=3)))
#
#         chats_to_get_summary = await chat_service.get_chats_id_to_get_summary(date_start=now - timedelta(days=1), date_end=now)
#         for chat in chats_to_get_summary:
#             summary = await summary_service.get_summary_chat(chat.id, date_start=now - timedelta(days=1), date_end=now)
#             msg = f"Саммари для чата \"{chat.title}\"\n"
#             for chat_to_send in chats_to_send_summary:
#                 await bot.send_message(chat_to_send.telegram_id, msg + summary.__str__(chat_id=chat.telegram_id), parse_mode=ParseMode.HTML)
#                 await asyncio.sleep(.25)
#
#

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import ClientSession
from app.db.database import async_session_maker
from app.services.chat_service import ChatService
from app.services.summary_service import SummaryService
from app.services.model_settings_service import ModelSettingsService
from app.services.llm_client import LLMClient
from app.core.config import settings
import asyncio
from datetime import datetime, timedelta, timezone
from loguru import logger

MAX_CONCURRENT_CHATS = 3
TELEGRAM_SEND_DELAY = 0.25
LLM_REQUEST_TIMEOUT = 180 * 3 # 3 попытки


async def _process_single_chat(
        bot: Bot,
        http_client: ClientSession,
        chat,
        date_start: datetime,
        date_end: datetime,
        chats_to_send: list,
        semaphore: asyncio.Semaphore,
) -> dict:
    chat_id = chat.id
    chat_title = chat.title
    result = {"chat_id": chat_id, "title": chat_title, "success": False, "error": None}

    async with semaphore:
        logger.info(f"🔄 [{chat_title}] Начало обработки (очередь: {semaphore._value}/{MAX_CONCURRENT_CHATS})")

        try:
            async with async_session_maker() as session:
                model = await ModelSettingsService(session).get_model()
                llm = LLMClient(
                    http_client=http_client,
                    api_key=settings.openrouter_api_key,
                    model_name=model.llm_id,
                    max_context_tokens=model.context_length,
                )
                summary_service = SummaryService(session, llm)

                summary = await summary_service.get_summary_chat(
                        chat_local_id=chat_id,
                        start_date=date_start,
                        end_date=date_end,
                    )

                # msg_prefix = f"📊 Саммари для чата \"{chat_title}\"\n\n"

                for target_chat in chats_to_send:
                    try:
                        await bot.send_message(
                            chat_id=target_chat.telegram_id,
                            text=summary,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                        await asyncio.sleep(TELEGRAM_SEND_DELAY)  # 🔹 Rate limit защита
                    except TelegramRetryAfter as e:
                        logger.warning(f"⏳ [{chat_title}] Rate limit: ждём {e.retry_after}с")
                        await asyncio.sleep(e.retry_after + 1)
                    except TelegramBadRequest as e:
                        logger.error(f"❌ [{chat_title}] Ошибка отправки в {target_chat.telegram_id}: {e}")
                        continue

                result["success"] = True
                logger.info(f"✅ [{chat_title}] Саммари отправлено в {len(chats_to_send)} чат(ов)")

        except asyncio.TimeoutError:
            error_msg = f"⏰ Таймаут генерации (> {LLM_REQUEST_TIMEOUT}с)"
            logger.error(f"❌ [{chat_title}] {error_msg}")
            result["error"] = error_msg

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            logger.exception(f"❌ [{chat_title}] Ошибка обработки: {error_msg}")
            result["error"] = error_msg

    return result


async def generate_daily_summary(bot: Bot, http_client: ClientSession):

    logger.info("🚀 Запуск ежедневной генерации саммари")

    now = datetime.now(timezone(timedelta(hours=3)))
    date_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    date_end = now.replace(hour=23, minute=59, second=59, microsecond=999999) - timedelta(days=1)

    async with async_session_maker() as session:
        chat_service = ChatService(session)
        chats_to_send = await chat_service.get_chats_to_send_summary()
        chats_to_process = await chat_service.get_chats_id_to_get_summary(
            date_start=date_start,
            date_end=date_end,
        )

    if not chats_to_process:
        logger.info("ℹ️ Нет чатов с сообщениями за период — ничего не генерируем")
        return

    if not chats_to_send:
        logger.warning("⚠️ Нет чатов для отправки саммари — пропускаем рассылку")
        return

    logger.info(f"📋 План: {len(chats_to_process)} чатов для генерации, {len(chats_to_send)} получателей")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHATS)

    tasks = [
        _process_single_chat(
            bot=bot,
            http_client=http_client,
            chat=chat,
            date_start=date_start,
            date_end=date_end,
            chats_to_send=chats_to_send,
            semaphore=semaphore,
        )
        for chat in chats_to_process
    ]

    start_time = asyncio.get_event_loop().time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = asyncio.get_event_loop().time() - start_time

    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    error_count = len(results) - success_count

    logger.info(f"🏁 Готово за {elapsed:.1f}с: ✅ {success_count} чатов, ❌ {error_count} ошибок")

    for r in results:
        if isinstance(r, Exception):
            logger.error(f"❌ Необработанное исключение: {r}")
        elif isinstance(r, dict) and not r["success"]:
            logger.warning(f"⚠️ {r['title']}: {r['error']}")
