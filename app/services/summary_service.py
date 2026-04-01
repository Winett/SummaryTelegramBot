from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Sequence
import json

from app.db.models import Message, Summary
from .llm_client import LLMClient, ChatMessage, ChatSummary, count_tokens
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
        smtm = select(Summary).where(Summary.chat_id == chat_db_id)
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
                Message.chat_id == chat_id,
                Message.sent_at >= date_start,
                Message.sent_at <= date_end,
            )
            .order_by(Message.sent_at.asc())
        )

        result = await self.db_session.execute(stmt)
        messages = result.scalars().all()

        logger.info(f"Загружено {len(messages)} сообщений для чата {chat_id}")
        return list(messages)

    async def _get_summaries_in_range(
        self,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> List[Summary]:
        stmt = (
            select(Summary)
            .where(
                Summary.chat_id == chat_id,
                Summary.period_start >= period_start,
                Summary.period_end <= period_end,
            )
            .order_by(Summary.period_start.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    def _format_summary_for_aggregation(self, summary: Summary) -> str:
        period_label = f"{summary.period_start.strftime('%d.%m')} — {summary.period_end.strftime('%d.%m')}"
        import re
        clean_content = re.sub(r'<[^>]+>', '', summary.content)
        return f"📅 {period_label}:\n{clean_content}"

    async def _aggregate_existing_summaries(
        self,
        chat_id: int,
        summaries: List[Summary],
        period_start: datetime,
        period_end: datetime,
    ) -> ChatSummary:

        max_input_tokens = self.llm_client.get_max_input_tokens()
        reserved_for_prompt = 800
        reserved_for_response = 1500
        safety_margin = int(max_input_tokens * 0.05)
        effective_limit = max_input_tokens - reserved_for_prompt - reserved_for_response - safety_margin

        aggregated_parts = []
        current_tokens = 0

        for summary in summaries:
            formatted = self._format_summary_for_aggregation(summary)
            line = f"\n\n{formatted}"
            line_tokens = count_tokens(line)

            if current_tokens + line_tokens > effective_limit:
                logger.warning(f"⚠️ Лимит токенов достигнут ({current_tokens}/{effective_limit}), обрезка агрегации")
                break

            aggregated_parts.append(formatted)
            current_tokens += line_tokens

        if not aggregated_parts:
            logger.warning("⚠️ Ни одно саммари не влезает, берём первое с токенизацией")
            first = summaries[0]
            clean = self._format_summary_for_aggregation(first)
            lines = clean.split('\n')
            safe_lines = []
            tokens = 0
            for line in lines:
                lt = count_tokens(line)
                if tokens + lt > effective_limit // 2:
                    break
                safe_lines.append(line)
                tokens += lt
            combined = '\n'.join(safe_lines)
        else:
            combined = "\n\n".join(aggregated_parts)

        period_label = f"{period_start.strftime('%Y-%m-%d')} — {period_end.strftime('%Y-%m-%d')}"

        prompt = f"""
            Ты — ассистент для агрегации саммари.
            Объедини следующие ежедневные отчёты в один итоговый за период {period_label}.
            Сохраняй структуру: темы, категории, открытые вопросы, следующие шаги.
            Отвечай СТРОГО в формате JSON.
            
            📋 ИСХОДНЫЕ САММАРИ:
            {combined}
            
            📝 ФОРМАТ ОТВЕТА (JSON):
            {{
              "chat_topic": "Основная тема чата",
              "categories": [
                {{
                  "name": "учеба",
                  "hashtag": "#учеба",
                  "emoji": "📚",
                  "topics": [
                    {{
                      "title": "Психология в КИУ: учеба и марафон",
                      "description": "Обсудили первый курс, дополнительные встречи и подготовку к 10-километровому марафону",
                      "message_count": 64,
                      "fire_count": 10,
                      "telegram_message_ids": [12345, 12346],
                      "relevance": "high"
                    }}
                  ]
                }}
              ],
              "open_questions": ["что уточнить"],
              "stats": {{"total_messages": {len(summaries)}, "period": "{period_label}"}}
            }}
        """
        prompt_tokens = count_tokens(prompt)
        if prompt_tokens > max_input_tokens:
            logger.error(f"❌ Промпт ({prompt_tokens}) > лимита ({max_input_tokens}), экстренная обрезка")
            combined = combined[-int(len(combined) * 0.7):]
            prompt = prompt.replace(f"📋 ИСХОДНЫЕ САММАРИ:\n{combined.split('📋')[0]}", f"📋 ИСХОДНЫЕ САММАРИ (сокращено):\n{combined}")

        raw_response = await self.llm_client._call_llm_with_retry(prompt, temperature=0.2)
        data = json.loads(raw_response)

        final_summary = ChatSummary(
            chat_topic=data.get("chat_topic", f"Итог за {period_label}"),
            categories=self.llm_client._parse_categories(data),
            open_questions=data.get("open_questions", []),
            stats={"source_summaries": len(summaries), "period": period_label},
        )

        await self._save_summary(chat_id, period_start, period_end, final_summary)

        return final_summary

    @staticmethod
    def _convert_to_chat_messages(db_messages: List[Message]) -> List[ChatMessage]:
        return [
            ChatMessage(
                message_id=msg.id,
                telegram_message_id=msg.telegram_message_id or 0,
                author_username=msg.user.username or f"user_{msg.user_id}",
                text=msg.text or "",
                sent_at=msg.sent_at.isoformat() if msg.sent_at else "",
            )
            for msg in db_messages
            if msg.text
        ]

    def _split_into_chunks(
            self,
            messages: List[ChatMessage],
    ) -> List[List[ChatMessage]]:
        if not messages:
            return []

        chunks = []
        current_chunk = []
        current_tokens = 0
        max_tokens_per_chunk = self.llm_client.get_max_input_tokens()

        for msg in messages:
            line = f"[{msg.sent_at}] @{msg.author_username} (msg_id:{msg.telegram_message_id}): {msg.text.strip()}"
            msg_tokens = count_tokens(line)

            if current_tokens + msg_tokens > max_tokens_per_chunk and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0

            current_chunk.append(msg)
            current_tokens += msg_tokens

        if current_chunk:
            chunks.append(current_chunk)

        logger.info(f"Разбито на {len(chunks)} чанков (всего {len(messages)} сообщений)")
        return chunks

    async def _save_summary(self, chat_id: int,
                            date_start: datetime,
                            date_end: datetime,
                            summary: ChatSummary
    ):
        for attempt in range(3):
            try:
                model_settings = await ModelSettingsService(self.db_session).get_model()
                summary_model = Summary(
                    chat_id=chat_id,
                    period_start=date_start,
                    period_end=date_end,
                    content=summary.__str__(chat_id=chat_id, use_html=True),
                    model_used=model_settings.name,
                )
                self.db_session.add(summary_model)
                await self.db_session.commit()
                return
            except Exception as e:
                await self.db_session.rollback()
                logger.warning(f"Попытка {attempt + 1} сохранения саммари failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        logger.error("❌ Не удалось сохранить саммари после 3 попыток")

    async def get_summary_chat(
            self,
            chat_id: int,
            date_start: datetime,
            date_end: datetime,
            force_single_chunk: bool = False,
            force_raw: bool = False,
    ) -> ChatSummary:
        model_settings = await ModelSettingsService(self.db_session).get_model()
        self.llm_client.model_name = model_settings.llm_id
        self.llm_client.max_context_tokens = model_settings.context_length

        is_single_day = date_start.date() == date_end.date()
        period_label = f"{date_start.strftime('%d.%m')}" if is_single_day else f"{date_start.strftime('%d.%m')}—{date_end.strftime('%d.%m')}"
        logger.info(f"📊 Запрос саммари: чат {chat_id}, период {period_label}, single_day={is_single_day}, force_raw={force_raw}")

        if is_single_day or force_raw:
            logger.info("✅ Стратегия: сырые сообщения за день")
            return await self._summarize_raw_messages(
                chat_id=chat_id,
                date_start=date_start,
                date_end=date_end,
                force_single_chunk=force_single_chunk,
            )

        existing_summaries = await self._get_summaries_in_range(chat_id, date_start, date_end)

        if existing_summaries and not force_raw:
            logger.info(f"✅ Найдено {len(existing_summaries)} саммари для агрегации")
            return await self._aggregate_existing_summaries(
                chat_id=chat_id,
                summaries=existing_summaries,
                period_start=date_start,
                period_end=date_end,
            )

        logger.warning(f"Генерируем с сообщений")
        return await self._summarize_raw_messages(
            chat_id=chat_id,
            date_start=date_start,
            date_end=date_end,
            force_single_chunk=force_single_chunk,
        )

    async def _summarize_raw_messages(
        self,
        chat_id: int,
        date_start: datetime,
        date_end: datetime,
        force_single_chunk: bool,
    ) -> ChatSummary:
        db_messages = await self._get_all_messages(chat_id, date_start, date_end)

        if not db_messages:
            logger.warning(f"Нет сообщений для чата {chat_id} в периоде {date_start} - {date_end}")
            return ChatSummary(
                chat_topic="Нет данных",
                open_questions=[],
                categories=[],
                stats={"error": "no_messages"}
            )

        chat_messages = self._convert_to_chat_messages(db_messages)

        if not chat_messages:
            return ChatSummary(
                chat_topic="Нет текстовых сообщений",
                categories=[],
                open_questions=[],
                stats={"error": "no_text_messages"}
            )

        period = f"{date_start.strftime('%Y-%m-%d')} — {date_end.strftime('%Y-%m-%d')}"

        if force_single_chunk or len(chat_messages) <= self.llm_client.max_context_tokens // 80:
            logger.info("Суммаризация в один проход")
            summary =  await self.llm_client.get_chunk_summary(
                messages=chat_messages,
                chunk_num=1,
                total_chunks=1,
                period=period,
            )
            await self._save_summary(chat_id=chat_id, summary=summary, date_start=date_start, date_end=date_end)
            return summary

        chunks = self._split_into_chunks(chat_messages)

        chunk_summaries: List[ChatSummary] = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Обработка чанка {i + 1}/{len(chunks)}")
            summary = await self.llm_client.get_chunk_summary(
                messages=chunk,
                chunk_num=i + 1,
                total_chunks=len(chunks),
                period=period,
            )
            chunk_summaries.append(summary)

        logger.info("Финальная агрегация чанков")
        final_summary = await self.llm_client.get_final_summary(
            chunk_summaries=chunk_summaries,
            total_messages=len(db_messages),
            period=period,
        )

        await self._save_summary(chat_id=chat_id, summary=final_summary, date_start=date_start, date_end=date_end)
        return final_summary