from dataclasses import dataclass, asdict, field
from typing import Optional, List, Literal
from aiohttp import ClientSession, ClientTimeout
import json
import tiktoken
import asyncio
from functools import lru_cache
from loguru import logger

@dataclass
class ChatMessage:
    message_id: int
    telegram_message_id: int
    author_username: str
    text: str
    sent_at: str  # ISO формат

    def format_for_prompt(self) -> str:
        return f"[{self.sent_at}] @{self.author_username} (msg_id:{self.telegram_message_id}): {self.text.strip()}"


@dataclass
class CategoryTopic:
    title: str
    description: str
    message_count: int = 0
    fire_count: int = 0
    telegram_message_ids: List[int] = field(default_factory=list)
    relevance: Literal["high", "medium", "low"] = "medium"


@dataclass
class Category:
    name: str
    hashtag: str
    emoji: str
    topics: List[CategoryTopic] = field(default_factory=list)

    def topic_count(self) -> int:
        return sum(t.message_count for t in self.topics)

    def fire_count(self) -> int:
        return sum(t.fire_count for t in self.topics)


@dataclass
class ChatSummary:
    chat_topic: str
    categories: List[Category]
    open_questions: List[str]
    # next_steps: List[dict]
    stats: dict = field(default_factory=dict)

    def total_messages(self) -> int:
        return sum(cat.topic_count() for cat in self.categories)

    def total_fire(self) -> int:
        return sum(cat.fire_count() for cat in self.categories)

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(
        self,
        chat_id: Optional[int] = None,
        limit_categories: int = 10,
        use_html: bool = True,
    ) -> str:
        if use_html:
            return self._format_html(chat_id, limit_categories)
        return self._format_markdown(chat_id, limit_categories)

    def _format_html(self, chat_id: Optional[int], limit: int) -> str:
        import html
        lines = [f"🔥 <b>{html.escape(self.chat_topic)}</b>", ""]

        for cat in self.categories[:limit]:
            lines.append(f"{cat.emoji} <b>{cat.hashtag} {html.escape(cat.name)}:</b>")
            for topic in cat.topics:
                lines.append(f"{html.escape(topic.title)}")
                lines.append(f"🔥 {topic.fire_count} 💬 {topic.message_count}")
                lines.append(html.escape(topic.description))
                if chat_id and topic.telegram_message_ids:
                    clean_id = str(chat_id).lstrip('-100')
                    link = f"https://t.me/c/{clean_id}/{topic.telegram_message_ids[0]}"
                    lines.append(f'<a href="{html.escape(link)}">[читать]</a>')
                lines.append("")
            lines.append("")

        if self.open_questions:
            lines.append("❓ <b>Открытые вопросы:</b>")
            for q in self.open_questions[:5]:
                lines.append(f"• {html.escape(q)}")
            lines.append("")

        return "\n".join(lines)

    def _format_markdown(self, chat_id: Optional[int], limit: int) -> str:
        return self._format_html(chat_id, limit)



@lru_cache(maxsize=4)
def _get_encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))



SUMMARY_PROMPT_CHUNK = """
Ты — ассистент для частичной суммаризации чата. Это блок {chunk_num} из {total_chunks}.

📋 ЗАДАЧА:
1. Сгруппируй сообщения по темам (учеба, нетворкинг, объявления, помощь и т.д.)
2. Для каждой темы выдели: заголовок, краткое описание, метрики
3. Привяжи telegram_message_id для ссылок на исходные сообщения
4. Игнорируй флуд, приветствия, пустые сообщения
5. Верни ответ СТРОГО в формате JSON

📝 ФОРМАТ ОТВЕТА (JSON):
{{
  "chat_topic": "общая тема блока",
  "categories": [
    {{
      "name": "учеба",
      "hashtag": "#учеба",
      "emoji": "📚",
      "topics": [
        {{
          "title": "Психология в КИУ: учеба и марафон",
          "description": "Обсудили первый курс и подготовку к марафону",
          "message_count": 64,
          "fire_count": 10,
          "telegram_message_ids": [12345, 12346],
          "relevance": "high"
        }}
      ]
    }}
  ],
  "open_questions": ["вопрос 1"]
}}

💬 ФРАГМЕНТ ЧАТА ({period}, {message_count} сообщений):
{chat_history}
"""

SUMMARY_PROMPT_FINAL = """
Ты — ассистент для итоговой суммаризации чата.

📋 ИНСТРУКЦИИ:
1. Объедини категории из всех чанков в логические группы
2. Для каждой категории объедини похожие темы, оставь самые релевантные
3. Подсчитай общие метрики (сообщения, реакции)
4. Выдели открытые вопросы и следующие шаги
5. Верни ответ СТРОГО в формате JSON
6. Возвращать СТРОГО в том формате, который указан ниже

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
  "stats": {{"total_messages": {message_count}, "period": "{period}"}}
}}

💬 ИСТОРИЯ ЧАТА (агрегированные чанки):
{chat_history}
"""



class LLMClient:

    def __init__(
        self,
        http_client: ClientSession,
        api_key: str,
        base_url: str = "https://routerai.ru/api/v1/",
        model_id: str = "google/gemini-2.0-flash-lite-001",
        max_context_tokens: int = 32000,
        max_retries: int = 3,
        reserved_for_response: int = 4000,
        safety_margin: float = 0.1,
    ):
        self.http_client = http_client
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_id
        self.max_context_tokens = max_context_tokens
        self.max_retries = max_retries
        self._reserved_for_response = reserved_for_response
        self._safety_margin = safety_margin

    def get_max_input_tokens(self) -> int:
        """Сколько токенов можно отправить в промпт."""
        return int(
            self.max_context_tokens * (1 - self._safety_margin)
            - self._reserved_for_response
        )

    def _build_timeout(self, prompt_tokens: int) -> ClientTimeout:
        """Динамический таймаут от размера промпта."""
        total = 180
        return ClientTimeout(
            total=total,
            connect=10,
            sock_connect=5,
            sock_read=180,
        )

    def _format_messages_for_prompt(
        self,
        messages: List[ChatMessage],
        max_tokens: int,
    ) -> tuple[str, int]:
        lines = []
        current_tokens = 0

        for msg in reversed(messages):
            line = msg.format_for_prompt()
            line_tokens = count_tokens(line)
            if current_tokens + line_tokens > max_tokens:
                logger.debug(f"Достигнут лимит токенов: {current_tokens}/{max_tokens}")
                break
            lines.append(line)
            current_tokens += line_tokens

        return "\n".join(reversed(lines)), len(lines)

    async def _call_llm_with_retry(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://your-bot-url.com",
            "X-Title": "Telegram Summary Bot",
        }
        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "Отвечай СТРОГО в формате JSON. Никакого лишнего текста."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        prompt_tokens = count_tokens(prompt)
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = self._build_timeout(prompt_tokens)
                logger.debug(f"LLM запрос (попытка {attempt}): {prompt_tokens} токенов, таймаут {timeout.total}с")

                async with self.http_client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=timeout,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"API error {response.status}: {error_text[:200]}")

                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                    if not content:
                        raise ValueError("Пустой ответ от LLM")

                    json.loads(content)
                    return content.strip()

            except asyncio.TimeoutError as e:
                logger.warning(f"⏰ Таймаут LLM (попытка {attempt}/{self.max_retries}): {e}")
                last_error = e
            except json.JSONDecodeError as e:
                logger.error(f"❌ LLM вернул невалидный JSON (попытка {attempt}): {e}")
                last_error = e
            except Exception as e:
                logger.warning(f"⚠️ Ошибка LLM (попытка {attempt}): {type(e).__name__}: {e}")
                last_error = e

            if attempt < self.max_retries:
                delay = 2.0 ** attempt
                logger.info(f"⏳ Ждём {delay:.1f}с перед повтором...")
                await asyncio.sleep(delay)

        raise RuntimeError(f"Не удалось получить ответ после {self.max_retries} попыток: {last_error}")

    def _parse_categories(self, data: dict) -> List[Category]:
        categories = []
        for cat_data in data.get("categories", []):
            topics = [
                CategoryTopic(
                    title=t["title"],
                    description=t["description"],
                    message_count=t.get("message_count", 0),
                    fire_count=t.get("fire_count", 0),
                    telegram_message_ids=t.get("telegram_message_ids", []),
                    relevance=t.get("relevance", "medium"),
                )
                for t in cat_data.get("topics", [])
                if isinstance(t.get("telegram_message_ids"), list)
            ]
            categories.append(Category(
                name=cat_data.get("name", "Общее"),
                hashtag=cat_data.get("hashtag", f"#{cat_data.get('name', 'общее')}"),
                emoji=cat_data.get("emoji", "💬"),
                topics=topics,
            ))
        return categories


    async def get_chunk_summary(
        self,
        messages: List[ChatMessage],
        chunk_num: int,
        total_chunks: int,
        period: str,
    ) -> ChatSummary:
        max_input = self.get_max_input_tokens()
        chat_history, used_count = self._format_messages_for_prompt(messages, max_input)

        prompt = SUMMARY_PROMPT_CHUNK.format(
            chunk_num=chunk_num,
            total_chunks=total_chunks,
            message_count=used_count,
            period=period,
            chat_history=chat_history,
        )

        raw_response = await self._call_llm_with_retry(prompt)
        data = json.loads(raw_response)

        return ChatSummary(
            chat_topic=data.get("chat_topic", "Без темы"),
            categories=self._parse_categories(data),
            open_questions=data.get("open_questions", []),
            stats={"chunk": chunk_num, "messages_processed": used_count},
        )

    async def get_final_summary(
        self,
        chunk_summaries: List[ChatSummary],
        total_messages: int,
        period: str,
    ) -> ChatSummary:
        all_categories: dict[str, Category] = {}
        for chunk in chunk_summaries:
            for cat in chunk.categories:
                key = cat.name.lower()
                if key not in all_categories:
                    all_categories[key] = Category(
                        name=cat.name,
                        hashtag=cat.hashtag,
                        emoji=cat.emoji,
                        topics=[],
                    )
                existing = {t.title.lower() for t in all_categories[key].topics}
                for topic in cat.topics:
                    if topic.title.lower() not in existing:
                        all_categories[key].topics.append(topic)
                        existing.add(topic.title.lower())

        total_topics = sum(len(c.topics) for c in all_categories.values())
        if len(all_categories) <= 3 and total_topics <= 15:
            return ChatSummary(
                chat_topic="Итоговое саммари",
                categories=list(all_categories.values()),
                open_questions=[],
                stats={"total_messages": total_messages, "period": period},
            )

        context_lines = []
        for cat in all_categories.values():
            context_lines.append(f"📁 {cat.emoji} {cat.hashtag} {cat.name}:")
            for topic in sorted(cat.topics, key=lambda t: -t.fire_count)[:10]:
                context_lines.append(
                    f"  • {topic.title} | 🔥{topic.fire_count} 💬{topic.message_count} | {topic.description}"
                )

        prompt = SUMMARY_PROMPT_FINAL.format(
            message_count=total_messages,
            period=period,
            chat_history="\n".join(context_lines[:300]),
        )

        raw_response = await self._call_llm_with_retry(prompt)
        data = json.loads(raw_response)

        return ChatSummary(
            chat_topic=data.get("chat_topic", "Агрегированная тема"),
            categories=self._parse_categories(data),
            open_questions=data.get("open_questions", []),
            stats={"total_messages": total_messages, "period": period},
        )

    async def get_balance(self) -> float:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self.http_client.get(f"{self.base_url}/credits", headers=headers) as response:
            data = await response.json()
            return float(data.get("data", {}).get("credits", -1))

    async def get_models(self) -> List[dict]:
        async with self.http_client.get(f"{self.base_url}/models") as response:
            return [
                {
                    "llm_id": obj.get("id", ""),
                    "name": obj.get("name", ""),
                    "context_length": int(obj.get("context_length", -1)),
                    "price_competition": float(obj.get("pricing", {}).get("completion", -1)),
                }
                for obj in (await response.json()).get("data", [])
            ]