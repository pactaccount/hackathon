"""
Robin Backend — TrueFoundry AI Gateway
Routes: Ollama (local) → Groq (free) → Pioneer (sponsor, default)
Smart Mode uses claude-sonnet-4-6 via Pioneer.
"""
import asyncio
import time
from enum import Enum

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from config import settings
import structlog

log = structlog.get_logger()


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    GROQ = "groq"
    PIONEER = "pioneer"
    AUTO = "auto"


class LLMResponse(BaseModel):
    content: str
    provider: LLMProvider
    model: str
    latency_ms: float = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class RobinGateway:
    """
    TrueFoundry-powered AI Gateway.
    Default: Pioneer (cloud, fast)
    Smart Mode: Pioneer with Claude Sonnet
    Future: Ollama (local, private)
    """

    def __init__(self):
        self._ollama = AsyncOpenAI(
            base_url=f"{settings.OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )
        self._groq = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.GROQ_API_KEY or "no-key",
        )
        self._pioneer = AsyncOpenAI(
            base_url=settings.PIONEER_BASE_URL,
            api_key=settings.PIONEER_API_KEY,
        )
        self._ollama_healthy: bool = False
        self._last_health_check: float = 0
        self._health_check_interval: float = 30

    async def _check_ollama_health(self) -> bool:
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return self._ollama_healthy
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                self._ollama_healthy = resp.status_code == 200
        except Exception:
            self._ollama_healthy = False
        self._last_health_check = now
        return self._ollama_healthy

    def _groq_available(self) -> bool:
        return bool(settings.GROQ_API_KEY)

    async def _select_provider(self, smart_mode: bool) -> LLMProvider:
        if settings.LLM_PROVIDER == LLMProvider.PIONEER or smart_mode:
            return LLMProvider.PIONEER
        if settings.LLM_PROVIDER == LLMProvider.GROQ:
            return LLMProvider.GROQ
        if settings.LLM_PROVIDER == LLMProvider.OLLAMA:
            return LLMProvider.OLLAMA
        # AUTO: Ollama → Groq → Pioneer
        if await self._check_ollama_health():
            return LLMProvider.OLLAMA
        if self._groq_available():
            return LLMProvider.GROQ
        return LLMProvider.PIONEER

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        smart_mode: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()
        provider = await self._select_provider(smart_mode)

        try:
            if provider == LLMProvider.OLLAMA:
                result = await self._chat_ollama(messages, tools)
            elif provider == LLMProvider.GROQ:
                result = await self._chat_groq(messages, tools)
            else:
                result = await self._chat_pioneer(messages, tools, smart_mode)

            result.latency_ms = (time.monotonic() - start) * 1000
            log.info("llm_response", provider=result.provider,
                     latency_ms=round(result.latency_ms, 1), tokens=result.completion_tokens)
            return result

        except Exception as e:
            if provider == LLMProvider.OLLAMA:
                log.warning("ollama_failed_fallback", error=str(e))
                self._ollama_healthy = False
                result = await self._chat_pioneer(messages, tools, smart_mode)
                result.latency_ms = (time.monotonic() - start) * 1000
                return result
            raise

    async def _chat_ollama(self, messages, tools):
        kwargs = dict(model=settings.OLLAMA_MODEL, messages=messages, temperature=0.7)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await self._ollama.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or str(choice.message.tool_calls or ""),
            provider=LLMProvider.OLLAMA, model=settings.OLLAMA_MODEL,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    async def _chat_groq(self, messages, tools):
        model = "llama-3.1-8b-instant"
        kwargs = dict(model=model, messages=messages, temperature=0.7)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await self._groq.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or str(choice.message.tool_calls or ""),
            provider=LLMProvider.GROQ, model=model,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    async def _chat_pioneer(self, messages, tools, smart_mode: bool = False):
        model = settings.PIONEER_SMART_MODEL if smart_mode else settings.PIONEER_MODEL
        kwargs = dict(model=model, messages=messages, temperature=0.7)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await self._pioneer.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or str(choice.message.tool_calls or ""),
            provider=LLMProvider.PIONEER, model=model,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )


gateway = RobinGateway()
