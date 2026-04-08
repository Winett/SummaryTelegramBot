from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelSettings

class ModelSettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def update_model(self, llm_id: str, name: str, context_length: int, price_competition: float) -> bool:
        model = await self.get_model()
        if model is None:
            return False

        model.llm_id = llm_id
        model.name = name
        model.context_length = context_length
        model.price_competition = price_competition
        try:
            await self.session.commit()
            return True
        except Exception:
            logger.error(f"Ошибка обновления модели для использования")
        return False

    async def update_promt(self, promt: str) -> bool:
        model = await self.get_model()
        model.promt = promt
        try:
            await self.session.commit()
            return True
        except Exception:
            logger.error(f"Ошибка при обновлении промта в нстройках")
            return False

    async def set_model_if_not_exists(self, llm_id: str, name: str, context_length: int, price_competition: float) -> bool:
        model = await self.get_model()
        if model:
            return True
        new_model = ModelSettings(llm_id=llm_id, name=name, context_length=context_length, price_competition=price_competition)
        self.session.add(new_model)
        try:
            await self.session.commit()
            return True
        except Exception:
            logger.error(f"Ошибка при установке модели")
        return False

    async def get_model(self) -> ModelSettings | None:
        model = await self.session.execute(select(ModelSettings))
        return model.scalar_one_or_none()
