"""Opt-in LLM explanation service.

LLM explanations are **not** part of the deterministic scoring core.  They are
opt-in, labeled advisory, and grounded in actual scoring records (the TF-IDF
matched terms).  If no LLM_API_KEY is configured the endpoint returns a clear
error — never a fabricated response.

Supported providers (all via httpx, server-side only):
  - openai-compatible  (OpenAI / LiteLLM / OpenRouter / Ollama chat)
  - anthropic          (Anthropic messages API)
  - gemini             (Google generateContent API)

Keys are never logged.  Timeouts are bounded.
"""
from __future__ import annotations

import asyncio
import json
import textwrap
from dataclasses import dataclass

import httpx


@dataclass
class LLMConfig:
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 10.0


class LLMError(Exception):
    """Raised when the LLM provider returns an error or is unavailable."""


class LLMAdvisor:
    """Grounded, opt-in LLM explanation for scoring results."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def available(self) -> bool:
        return bool(self.config.api_key)

    async def explain_scoring(
        self,
        posting_title: str,
        posting_company: str,
        matched_terms: list[str],
        score: float,
    ) -> str:
        """Generate an advisory explanation grounded in matched TF-IDF terms.

        Builds a prompt that includes only the actual matched terms and score
        — the LLM never sees raw posting content beyond title/company.
        """
        if not self.available():
            raise LLMError(
                "LLM explanation is opt-in and no LLM_API_KEY is configured. "
                "Set LLM_API_KEY to enable."
            )
        terms = ", ".join(matched_terms) if matched_terms else "(none)"
        system = textwrap.dedent(
            """\
            You are an expert technical recruiter assistant.  You explain why
            a job posting matched (or did not match) a target role profile,
            based ONLY on the evidence provided.  Be concise and specific.
            Never fabricate facts about the posting.  Label any speculation
            as advisory.
            """
        )
        user = (
            f"Posting: {posting_title} at {posting_company}\n"
            f"Relevance score (0-1): {score:.3f}\n"
            f"TF-IDF matched terms from the target profile: {terms}\n\n"
            "In two sentences, explain why this posting matched or did not match."
        )
        return await self._call(system, user)

    async def _call(self, system: str, user: str) -> str:
        provider = self.config.provider.lower()
        if provider in ("openai-compatible", "openai", "ollama", "litellm", "openrouter"):
            return await self._openai(system, user)
        if provider == "anthropic":
            return await self._anthropic(system, user)
        if provider == "gemini":
            return await self._gemini(system, user)
        raise LLMError(f"Unsupported LLM provider: {provider}")

    async def _openai(self, system: str, user: str) -> str:
        url = (self.config.base_url or "https://api.openai.com/v1") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        payload = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 256,
            "temperature": 0.0,
        }
        return await self._request_json(url, headers, payload, self._extract_openai)

    async def _anthropic(self, system: str, user: str) -> str:
        url = (self.config.base_url or "https://api.anthropic.com/v1") + "/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": user}],
            "system": system,
        }
        return await self._request_json(url, headers, payload, self._extract_anthropic)

    async def _gemini(self, system: str, user: str) -> str:
        base = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{self.config.model}:generateContent"
        params = {"key": self.config.api_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": system + "\n\n" + user}]}],
            "generationConfig": {"maxOutputTokens": 256, "temperature": 0.0},
        }
        return await self._request_json(url, {}, payload, self._extract_gemini, params=params)

    async def _request_json(
        self,
        url: str,
        headers: dict,
        payload: dict,
        extractor: "callable",
        params: dict | None = None,
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.config.timeout_seconds)) as client:
                resp = await client.post(url, headers=headers, json=payload, params=params)
                if resp.status_code != 200:
                    # Redact the API key from the error message.
                    detail = resp.text[:200]
                    raise LLMError(f"Provider returned HTTP {resp.status_code}: {detail}")
                data = resp.json()
                return extractor(data)
        except httpx.TimeoutException:
            raise LLMError("LLM request timed out")
        except json.JSONDecodeError:
            raise LLMError("Provider returned invalid JSON")
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}")

    @staticmethod
    def _extract_openai(data: dict) -> str:
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _extract_anthropic(data: dict) -> str:
        return data["content"][0]["text"].strip()

    @staticmethod
    def _extract_gemini(data: dict) -> str:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


__all__ = ["LLMConfig", "LLMAdvisor", "LLMError"]