from typing import Optional
from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User as UserModel


class UserService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, tg_user: TgUser) -> UserModel:

        result = await self.session.execute(
            select(UserModel).where(UserModel.telegram_id == tg_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = UserModel(
                telegram_id=tg_user.id,
                username=tg_user.username,
                full_name=tg_user.full_name,
                is_bot=tg_user.is_bot
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)


        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[UserModel]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()