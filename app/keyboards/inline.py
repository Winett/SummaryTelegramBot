from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def approve_chat_keyboard(tg_chat_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="✅ Одобрить чат",
            callback_data=f"approve_chat_{tg_chat_id}"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="❌ Отклонить чат",
            callback_data=f"disapprove_chat_{tg_chat_id}"
        )
    )
    return keyboard.as_markup()

def chats_keyboard(chats: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for tg_chat_id, chat_name in chats:
        keyboard.row(
            InlineKeyboardButton(
                text=chat_name,
                callback_data=f"chat_{tg_chat_id}"
            )
        )
    return keyboard.as_markup()

def work_with_chat(tg_chat_id: int, actived_chat: bool, approved_chat: bool, to_send_summary: bool = False):
    keyboard = InlineKeyboardBuilder()

    if actived_chat:
        actived_chat_button = InlineKeyboardButton(
            text=f"❌ Деактивировать чат",
            callback_data=f"disactive_chat_{tg_chat_id}"
        )
    else:
        actived_chat_button = InlineKeyboardButton(
            text=f"✅ Активировать чат",
            callback_data=f"active_chat_{tg_chat_id}"
        )

    if approved_chat:
        approved_chat_button = InlineKeyboardButton(
            text=f"❌ Отозвать",
            callback_data=f"disapprove_chat_{tg_chat_id}"
        )
    else:
        approved_chat_button = InlineKeyboardButton(
            text="✅ Подтердить",
            callback_data=f"approve_chat_{tg_chat_id}"
        )
    if to_send_summary:
        keyboard.add(
            InlineKeyboardButton(
                text="Перестать выссылать саммари в этот чат",
                callback_data=f"to_send_chat_active_{tg_chat_id}"
            )
        )
    else:
        keyboard.add(
            InlineKeyboardButton(
                text="Сделать чат для отсылки саммари",
                callback_data=f"to_send_chat_deactive_{tg_chat_id}"
            )
        )


    keyboard.row(actived_chat_button, approved_chat_button)

    keyboard.row(
        InlineKeyboardButton(
            text="📊 Саммари вручную",
            callback_data=f"sum_manual_{tg_chat_id}"
        ),
    )
    keyboard.row(
        InlineKeyboardButton(
            text="Обновить",
            callback_data=f"refresh_refresh_work_chat_{tg_chat_id}"
        )
    )

    return keyboard.as_markup()

def admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text="📂 Работа с чатами",
            callback_data="work_with_chats"
        )
    )

    keyboard.row(
        InlineKeyboardButton(
            text="🤖 Администраторы",
            callback_data="work_with_admins"
        )
    )

    keyboard.row(
        InlineKeyboardButton(
            text="⚙️ Настройка нейросети",
            callback_data="llm_settings"
        )
    )

    return keyboard.as_markup()
def work_with_admins():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="➕ Добавить админа",
            callback_data="add_admin"
        ),
        InlineKeyboardButton(
            text="➖ Удалить админа",
            callback_data="remove_admin"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="Список админов",
            callback_data="list_admin"
        )
    )
    return keyboard.as_markup()

def work_with_llm_settings():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="Обновить модель",
            callback_data="llm_update_model"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="Работа с промтом",
            callback_data="llm_promt"
        )
    )

    return keyboard.as_markup()

def update_llm_promt_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="Обновить промт",
            callback_data="update_llm_promt"
        )
    )

    return keyboard.as_markup()

def cancel_keyboad():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="Отмена",
            callback_data="cancel"
        )
    )
    return keyboard.as_markup()