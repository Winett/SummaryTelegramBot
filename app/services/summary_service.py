from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Sequence
import json

from app.db.models import Message, Summary, Chat
from . import llm_client
from .llm_client import LLMClient, count_tokens
from loguru import logger
from app.services.model_settings_service import ModelSettingsService
import asyncio


class SummaryService:

    def __init__(
            self,
            db_session: AsyncSession,
            llm_client: LLMClient,
    ):
        self.db_session = db_session
        self.llm_client = llm_client

    async def get_summaries_for_chat_from_db(self, chat_db_id: int, start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[Summary]:
        smtm = select(Summary).where(chat_db_id == Summary.chat_id)
        if start_date:
            smtm = smtm.where(Summary.period_start >= start_date)
        if end_date:
            smtm = smtm.where(Summary.period_end <= end_date)
        res = await self.db_session.execute(smtm)
        return res.scalars().all()
    async def _get_all_messages(
            self,
            chat_id: int,
            date_start: datetime,
            date_end: datetime,
    ) -> List[Message]:
        stmt = (
            select(Message)
            .options(selectinload(Message.user), selectinload(Message.chat))
            .where(
                chat_id == Message.chat_id,
                Message.sent_at >= date_start,
                Message.sent_at <= date_end,
            )
            .options(selectinload(Message.user), selectinload(Message.chat))
            .order_by(Message.sent_at.asc())
        )

        result = await self.db_session.execute(stmt)
        messages = result.scalars().all()

        logger.info(f"Загружено {len(messages)} сообщений для чата {chat_id}")
        return list(messages)

    @staticmethod
    def _prepare_telegram_id_for_llm(tg_id: int | str) -> str:
        tg_id = str(tg_id)
        if tg_id.startswith("-100"):
            return tg_id[4:]
        if tg_id.startswith("-"):
            return tg_id[1:]
        return tg_id

    async def save_summary(self, summary: Summary) -> bool:
        self.db_session.add(summary)
        try:
            await self.db_session.commit()
            return True
        except Exception:
            await self.db_session.rollback()
            return False




    async def get_summary_chat(
            self,
            chat_local_id: int,
            start_date: datetime,
            end_date: datetime,
    ) -> str:
        chat: Chat = (await self.db_session.execute(
            select(Chat).where(chat_local_id == Chat.id)
        )).scalar()

        llm_settings = await ModelSettingsService(self.db_session).get_model()

        promt = f"Название телеграм чата: {chat.title}; telegram_id чата: {self._prepare_telegram_id_for_llm(chat.telegram_id)}\nОтвечать на русском языке.\n\n" + llm_settings.promt


        now_context_lenght = count_tokens(promt)

        messages = await self._get_all_messages(chat.id, start_date, end_date)

        msgs = []
        for message in messages:
            if now_context_lenght + count_tokens(message.message_to_llm + "\n") < self.llm_client.max_input_tokens():
                msgs.append(message.message_to_llm)
            else:
                break
        promt += f"История чата: {'\n'.join(msgs)}"
        try:
            answer = await self.llm_client.completions(promt)
            summary = Summary(
                chat_id=chat.id,
                period_start=start_date,
                period_end=end_date,
                content=answer,
                model_used=llm_settings.llm_id,
            )
            await self.save_summary(summary)
            return answer
        except ValueError as e:
            logger.warning(e)
            raise



