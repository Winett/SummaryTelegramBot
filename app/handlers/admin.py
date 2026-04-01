from aiogram.enums import ChatType
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import chats_keyboard, work_with_chat, admin_keyboard, work_with_admins, work_with_llm_settings

from app.states.admin import AdminAddState, AdminRemoveState
from aiogram.fsm.context import FSMContext
from aiogram import Router, F
from aiogram.filters import Command

from ..services.admin_service import AdminService
from ..services.chat_service import ChatService
from ..services.llm_service import LLMService
from ..services.model_settings_service import ModelSettingsService
from app.states.llm_settings import SettingModelLLMState

from app.core.config import settings

admin_router = Router()

@admin_router.message(Command("admin"))
async def admin(message: Message, chat_service: ChatService):
    await message.answer(f"Панель администрирования", reply_markup=admin_keyboard())

@admin_router.callback_query(F.data.contains("work_with_admins"))
async def admin_work_admins(query: CallbackQuery):
    await query.answer()
    await query.message.answer("Работа с администраторами:", reply_markup=work_with_admins())

@admin_router.callback_query(F.data.contains("add_admin"))
async def add_admin(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(AdminAddState.add_admin)
    await query.message.answer("Перешлите любое сообщение от пользователя, которого хотите сделать администратором")

@admin_router.message(AdminAddState.add_admin)
async def add_admin_user(message: Message, state: FSMContext, admin_service: AdminService):
    if not message.forward_from:
        await state.clear()
        if message.forward_origin and message.forward_origin.type == "hidden_user":
            await message.answer("Не возможно добавить данного пользователя в администраторы, так как у него скрыт аккаунт при перессылке сообщений")
        else:
            await message.answer("Данное сообщение не является пересланным")
        return
    forwarded_user = message.forward_from
    admin = await admin_service.get_admin(forwarded_user.id)
    if admin:
        await message.answer("Данный пользователь уже является администратором")
        return
    await admin_service.add_admin(forwarded_user)
    await message.answer(f"Новый администратор id={forwarded_user.id} username={forwarded_user.username} \
    fullname={forwarded_user.full_name} успешно добавлен")
    await state.clear()


@admin_router.callback_query(F.data.contains("remove_admin"))
async def remove_admin(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(AdminRemoveState.remove_admin)
    await query.message.answer("Перешлите любое сообщение от пользователя, которого хотите удалить из администраторов")

@admin_router.message(AdminRemoveState.remove_admin)
async def remove_admin_user(message: Message, state: FSMContext, admin_service: AdminService):
    if not message.forward_from:
        await state.clear()
        if message.forward_origin and message.forward_origin.type == "hidden_user":
            await message.answer(
                "Не возможно добавить данного пользователя в администраторы, так как у него скрыт аккаунт при перессылке сообщений")
        else:
            await message.answer("Данное сообщение не является пересланным")
        return
    forwarded_user = message.forward_from
    admin = await admin_service.get_admin(forwarded_user.id)
    if not admin:
        await state.clear()
        await message.answer(f"Данный пользователь id={forwarded_user.id} username={forwarded_user.username} fullname={forwarded_user.full_name} не был администратором")
        return
    await admin_service.remove_admin(forwarded_user.id)
    await message.answer("Админ успешно удалён")


@admin_router.callback_query(F.data.contains("list_admin"))
async def list_admin(query: CallbackQuery, admin_service: AdminService):
    await query.answer()
    admins = await admin_service.get_admins()
    msg = "Список администраторов:\n\n"
    for admin in admins:
        msg += f"id={admin.telegram_id} username=@{admin.username} fullname={admin.full_name}\n"
    await query.message.answer(msg)

@admin_router.callback_query(F.data.contains("work_with_chats"))
async def admin_work_chats(query: CallbackQuery, chat_service: ChatService):
    await query.answer()
    chats = await chat_service.get_chats_telegram_id_and_title()
    await query.message.answer("Работа с чатами", reply_markup=chats_keyboard(chats))

@admin_router.callback_query(F.data.startswith("chat"))
async def admin_work_chat(query: CallbackQuery, chat_service: ChatService):
    tg_chat_id = query.data.split("_")[-1]
    if not tg_chat_id:
        await query.answer(f"Ошибка передачи параметра")
        return

    tg_chat_id = int(tg_chat_id)
    chat = await chat_service.get_chat_by_telegram_id(tg_chat_id)

    await query.message.edit_text(chat.chat_info,
                                  reply_markup=work_with_chat(tg_chat_id, chat.is_active, chat.is_approved, chat.to_send_summary))

@admin_router.callback_query(F.data.contains("refresh_work_chat"))
async def refresh_admin_work_chat(query: CallbackQuery, chat_service: ChatService):
    try:
        await query.answer()
        await admin_work_chat(query, chat_service)
    except Exception as e:
        pass


@admin_router.callback_query(F.data.contains("llm_settings"))
async def admin_settings(query: CallbackQuery, model_settings_service: ModelSettingsService, llm_service: LLMService):
    await query.answer()
    current_model = await model_settings_service.get_model()

    balance = await llm_service.get_balance()

    await query.message.answer(f"Текущие настройки модели: \n\n"
                               f"id: '<code>{current_model.llm_id}</code>'\n"
                               f"Название: {current_model.name}\n"
                               f"Цена за 1М исходящих токенов: {current_model.price_competition*10**6:.0f}₽\n"
                               f"Длина контекста: {current_model.context_length}\n\n"
                               f"API ключ: {settings.openrouter_api_key[:5]}...{settings.openrouter_api_key[-5:]}\n"
                               f"Текущий баланс: {balance}₽",
                               parse_mode="HTML", reply_markup=work_with_llm_settings())

@admin_router.callback_query(F.data.contains("llm_update_model"))
async def llm_update_model(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.answer(f"Отправьте id модели из сайта https://routerai.ru/models", disable_web_page_preview=True)
    await state.set_state(SettingModelLLMState.waiting_for_model)

@admin_router.message(SettingModelLLMState.waiting_for_model)
async def llm_update_model(message: Message, state: FSMContext, model_settings_service: ModelSettingsService, llm_service: LLMService):
    await state.clear()
    model_to_use = message.text
    models = await llm_service.get_models()
    for model in models:
        if model_to_use == model["llm_id"]:
            await model_settings_service.update_model(**model)
            await message.answer("Новая модель установлена")
            return
    await message.answer("Не удалось найти такую модель")



