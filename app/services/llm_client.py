# llm_client.py
from __future__ import annotations

import asyncio
from loguru import logger
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional, Literal

import aiohttp
import tiktoken
from aiohttp import ClientSession, ClientResponse, ClientTimeout



MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: MessageRole
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class CompletionRequest:
    messages: list[Message]
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        return payload


class LLMClientError(Exception):
    """Базовое исключение клиента."""
    pass


# ─────────────────────────────────────────────────────
# Токенизация (tiktoken)
# ─────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _get_encoder(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    if not text:
        return 0
    return len(_get_encoder(encoding_name).encode(text))


def count_messages_tokens(
    messages: list[Message],
    model: str,
    encoding_name: str = "cl100k_base",
) -> int:
    tokens_per_message = 3  # role + content + separator
    tokens_per_name = 1
    encoder = _get_encoder(encoding_name)

    total = 0
    for msg in messages:
        total += tokens_per_message
        total += len(encoder.encode(msg.content))
        total += len(encoder.encode(msg.role))
        if msg.role == "system":  # системные сообщения могут иметь доп. вес
            total += 1

    total += 3  # финальный separator для assistant
    return total


class LLMClient:

    def __init__(
        self,
        http_client: ClientSession,
        api_key: str,
        base_url: str = "https://routerai.ru/api/v1/",
        model_name: str = "gpt-4o-mini",
        max_context_tokens: int = 128_000,
        max_output_tokens: int = 4096,
        token_buffer_fraction: float = 0.1,
        encoding_name: str = "cl100k_base",
        retries: int = 3,
        retry_backoff: float = 1.0,
        default_timeout: float = 240.0,
    ):
        if not base_url.endswith("/"):
            base_url += "/"
        if not (0.0 <= token_buffer_fraction < 1.0):
            raise ValueError("token_buffer_fraction must be in [0.0, 1.0)")

        self._session = http_client
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = model_name
        self._max_context_tokens = max_context_tokens
        self._max_output_tokens = max_output_tokens
        self._token_buffer_fraction = token_buffer_fraction
        self._encoding_name = encoding_name
        self._retries = retries
        self._retry_backoff = retry_backoff
        self._default_timeout = default_timeout

        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }


    def max_input_tokens(self, output_tokens: Optional[int] = None) -> int:
        output = output_tokens or self._max_output_tokens
        buffer = int(self._max_context_tokens * self._token_buffer_fraction)
        available = self._max_context_tokens - output - buffer
        return max(0, available)

    async def completions(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        pre_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        model = model or self._default_model
        temperature = temperature if temperature is not None else 0.3
        timeout = timeout or self._default_timeout
        max_tokens = max_tokens or self._max_output_tokens

        messages: list[Message] = []
        if pre_prompt:
            messages.append(Message(role="system", content=pre_prompt))
        messages.append(Message(role="user", content=prompt))

        estimated_input = count_messages_tokens(messages, model, self._encoding_name)
        available_input = self.max_input_tokens(output_tokens=max_tokens)

        if estimated_input > available_input:
            raise LLMClientError(
                f"Input tokens ({estimated_input}) exceed available limit ({available_input}). "
                f"Consider truncating prompt or reducing max_tokens."
            )

        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        answer = await self._request_with_retry(
            method="POST",
            endpoint="chat/completions",
            payload=request.to_payload(),
            timeout=timeout,
        )

        content = answer.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("Пустой ответ от LLM")

        return content

    async def get_balance(self, endpoint: str = "credits") -> float:
        response = await self._request_with_retry(
            method="GET",
            endpoint=endpoint,
            timeout=self._default_timeout,
        )
        balance = response.get("data", {}).get(endpoint, 0)
        if balance is None:
            raise LLMClientError(f"Unexpected balance response: {response}")
        return float(balance)

    async def get_models(self) -> list[dict[str, Any]]:
        response = await self._request_with_retry(
            method="GET",
            endpoint="models",
            timeout=self._default_timeout,
        )
        models = response.get("data", response)
        if not isinstance(models, list):
            raise LLMClientError(f"Unexpected models response: {response}")
        return models


    async def _request_with_retry(
        self,
        method: Literal["GET", "POST"],
        endpoint: str,
        payload: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{endpoint.lstrip('/')}"
        last_exception: Optional[Exception] = None

        for attempt in range(self._retries + 1):
            try:
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    json=payload if method == "POST" else None,
                    timeout=ClientTimeout(total=timeout),
                ) as response:
                    return await self._handle_response(response)

            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                last_exception = e
                logger.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._retries + 1,
                    e,
                )
            except aiohttp.ClientResponseError as e:
                if 500 <= e.status < 600:
                    last_exception = e
                    logger.warning(
                        "Server error %d (attempt %d/%d): %s",
                        e.status,
                        attempt + 1,
                        self._retries + 1,
                        e,
                    )
                else:
                    error_body = await e.read() if e.headers.get("Content-Length") else b""
                    raise LLMClientError(
                        f"API error {e.status}: {e.message}. Body: {error_body.decode()[:200]}"
                    ) from e
            except Exception as e:
                last_exception = e
                logger.exception("Unexpected error during request")

            if attempt < self._retries:
                delay = self._retry_backoff * (2 ** attempt)
                logger.debug("Retrying in %.2fs...", delay)
                await asyncio.sleep(delay)

        raise LLMClientError(
            f"Request failed after {self._retries + 1} attempts"
        ) from last_exception

    async def _handle_response(self, response: ClientResponse) -> dict[str, Any]:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            text = await response.text()
            raise LLMClientError(
                f"Expected JSON response, got: {content_type}. Body: {text[:200]}"
            )

        data = await response.json()

        if response.status >= 400:
            if isinstance(data, dict):
                error = data.get("error", {})
                error_msg = error.get("message", str(data)) if isinstance(error, dict) else str(data)
            else:
                error_msg = str(data)
            raise LLMClientError(f"API error {response.status}: {error_msg}")

        return data