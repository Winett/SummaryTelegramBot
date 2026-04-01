from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram.enums import ChatType



class ChatFilter(BaseFilter):
    async def __call__(self, message: Message):
        return message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
