from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from aiogram import Router, F
from asyncio import TimeoutError
from loguru import logger

from app.db.models import Message
from app.keyboards.inline import work_with_chat
from app.states.summary import SummaryManualState
from app.services.chat_service import ChatService
from app.services.summary_service import SummaryService

from datetime import datetime, timedelta, timezone

callback_query_router = Router()


@callback_query_router.callback_query(F.data.startswith("approve_chat_"))
async def approve_chat_callback(query: CallbackQuery, chat_service: ChatService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.approve_chat_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка при одобрении", show_alert=True)
            return

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        try:
            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

        await query.answer("✅ Чат одобрен!")
        logger.info(f"Чат {tg_chat_id} одобрен админом {query.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при одобрении: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


@callback_query_router.callback_query(F.data.startswith("disapprove_chat_"))
async def disapprove_chat_callback(query: CallbackQuery, chat_service: ChatService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.disapprove_chat_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка", show_alert=True)
            return

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        try:
            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

        await query.answer("✅ Статус изменён")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


@callback_query_router.callback_query(F.data.startswith("active_chat_"))
async def activate_chat_callback(query: CallbackQuery, chat_service: ChatService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.active_chat_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка", show_alert=True)
            return

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        try:
            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

        await query.answer("✅ Активирован")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


@callback_query_router.callback_query(F.data.startswith("disactive_chat_"))
async def deactivate_chat_callback(query: CallbackQuery, chat_service: ChatService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.deactivate_chat_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка", show_alert=True)
            return

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        try:
            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

        await query.answer("✅ Деактивирован")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)

@callback_query_router.callback_query(F.data.startswith("to_send_chat_active_"))
async def active_to_send_chat(query: CallbackQuery, chat_service: ChatService):
    try:

        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.deactive_chat_to_send_summary_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка", show_alert=True)
            return
        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        try:

            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


@callback_query_router.callback_query(F.data.startswith("to_send_chat_deactive_"))
async def deactive_to_send_chat(query: CallbackQuery, chat_service: ChatService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        success = await chat_service.active_chat_to_send_summary_by_telegram_id(tg_chat_id)
        if not success:
            await query.answer("❌ Ошибка", show_alert=True)
            return
        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)
        try:
            await query.message.edit_text(
                chat.chat_info,
                parse_mode="HTML",
                reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary)
            )
        except TelegramBadRequest:
            pass

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)

@callback_query_router.callback_query(F.data.startswith("summary_today"))
async def summary_today(query: CallbackQuery, state: FSMContext, chat_service: ChatService, summary_service: SummaryService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)
        now = datetime.now(timezone(timedelta(hours=3))) - timedelta(days=2)
        await query.message.edit_text("⏳ Ожидание ответа от нейронки...")
        response = await summary_service.get_summary_chat(chat_id=chat.id, date_start=now.replace(hour=0, minute=0, second=0, microsecond=0), date_end=now)

        try:
            await query.message.edit_text(
                # response
                "Получено новое саммари"
            )
        except TelegramBadRequest:
            pass


    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.message.edit_text("❌ Ошибка при обработке нейронкой", show_alert=True)

@callback_query_router.callback_query(F.data.startswith("summary_week"))
async def summary_today(query: CallbackQuery, state: FSMContext, chat_service: ChatService, summary_service: SummaryService):
    try:
        tg_chat_id = int(query.data.split("_")[-1])
        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

        now = datetime.now(timezone(timedelta(hours=3)))

        days_since_monday = now.weekday()
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)

        await query.message.edit_text("⏳ Ожидание ответа от нейронки...")

        try:
            response = await summary_service.get_summary_chat(
                chat_id=chat.id,
                date_start=week_start,
                date_end=now
            )
        except TimeoutError:
            await query.message.edit_text("❌ Вышло время генерации")
            return

        try:
            await query.message.edit_text(
                # response,
                "Получено новое саммари"
            )
        except TelegramBadRequest:
            pass



    except Exception as e:
        logger.error(f"Ошибка: {e}")
        try:
            await query.message.edit_text("❌ Ошибка при обработке нейронкой")
        except TelegramBadRequest:
            pass
        await query.answer("❌ Ошибка", show_alert=True)

@callback_query_router.callback_query(F.data == "ignore")
async def ignore(query: CallbackQuery):
    await query.answer()


@callback_query_router.callback_query(F.data.startswith("sum_manual_"))
async def start_manual_summary(
        query: CallbackQuery,
        state: FSMContext,
        chat_service: ChatService,
):
    await query.answer()

    try:
        tg_chat_id = int(query.data.split("_")[-1])

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)
        if not chat:
            await query.message.answer("❌ Чат не найден в базе")
            return

        await state.update_data({
            "tg_chat_id": tg_chat_id,
            "chat_db_id": chat.id,
        })

        await query.message.answer(
            "📅 <b>Генерация саммари</b>\n\n"
            "Введите период в формате:\n"
            "<code>ДД.ММ.ГГГГ-ДД.ММ.ГГГГ</code>\n\n"
            "Пример: <code>30.03.2026-30.03.2026</code>\n\n"
            "❌ /cancel — отменить",
            parse_mode="HTML"
        )

        await state.set_state(SummaryManualState.waiting_for_date)


    except ValueError:
        logger.error(f"❌ Неверный chat_id в callback: {query.data}")
        await query.message.answer("❌ Ошибка: некорректный ID чата")
    except Exception as e:
        logger.exception(f"❌ Ошибка старта саммари: {e}")
        await query.message.answer("❌ Произошла ошибка при запуске")


@callback_query_router.message(SummaryManualState.waiting_for_date)
async def process_manual_summary_date(
        message: Message,
        state: FSMContext,
        summary_service: SummaryService,
        chat_service: ChatService,
):

    data = await state.get_data()
    tg_chat_id = data.get("tg_chat_id")
    chat_db_id = data.get("chat_db_id")

    if not chat_db_id:
        await message.answer("❌ Ошибка: контекст потерян. Начните заново.")
        await state.clear()
        return

    date_range = message.text.strip()
    parsed = parse_date_range(date_range)

    if not parsed:
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Используйте: <code>ДД.ММ.ГГГГ-ДД.ММ.ГГГГ</code>\n"
            "Пример: <code>30.03.2026-30.03.2026</code>",
            parse_mode="HTML"
        )
        return

    date_start, date_end = parsed


    summaries_db = await summary_service.get_summaries_for_chat_from_db(chat_db_id, date_start, date_end)
    if not summaries_db and date_start.date() != date_end.date():
        await message.answer(f"Не найден ни один промежуточный саммари, для начала сделайте промежуточный саммари")
        return

    if summaries_db and date_start.date() == date_end.date():
        await message.answer(summaries_db[0].content, parse_mode="HTML", disable_web_page_preview=True)
        await message.answer(f"Данные взяты из БД")
        return

    if (date_end - date_start).days > 31:
        await message.answer("❌ Максимальный период — 31 дней")
        return

    progress_msg = await message.answer("🔄 Генерирую саммари...\n\n⏳ Это может занять 1-3 минуты")

    try:
        summary = await summary_service.get_summary_chat(
            chat_id=chat_db_id,  # ✅ ID в БД
            date_start=date_start,
            date_end=date_end,
        )

        chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)
        message_text = f"Саммари для чата \"{chat.title}\"\n" + summary.__str__(chat_id=tg_chat_id)

        await message.answer(
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        await progress_msg.delete()

        logger.info(f"✅ Ручное саммари для чата {tg_chat_id}: {date_start} - {date_end}")

    except Exception as e:
        logger.exception(f"❌ Ошибка генерации саммари: {e}")
        await progress_msg.delete()
        await message.answer(
            f"❌ Ошибка при генерации саммари:\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            "Попробуйте уменьшить период или повторить позже.",
            parse_mode="HTML"
        )

    finally:
        await state.clear()


def parse_date_range(date_str: str) -> tuple[datetime, datetime] | None:
    try:
        parts = date_str.split("-")
        if len(parts) != 2:
            return None

        start_str, end_str = parts

        date_start = datetime.strptime(start_str.strip(), "%d.%m.%Y")
        date_end = datetime.strptime(end_str.strip(), "%d.%m.%Y")

        if date_start > date_end:
            return None

        date_start = date_start.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        return date_start, date_end

    except (ValueError, IndexError):
        return None

@callback_query_router.message(SummaryManualState.waiting_for_date, F.text == "/cancel")
async def cancel_manual_summary(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Отменено")
