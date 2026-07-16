from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import request


FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)


def verify_quote(quote: str | None, source_text: str | None) -> bool:
    if not quote or not source_text:
        return False
    normalized_quote = re.sub(r"\s+", " ", quote).strip()
    normalized_source = re.sub(r"\s+", " ", source_text).strip()
    return normalized_quote in normalized_source


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    stripped = FENCE_PATTERN.sub("", stripped).strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
    return stripped.strip()


class LLMClient:
    def __init__(self, config: Any):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency_limit)
        self.call_count = 0
        self.token_count = 0
        self.mock_llm = bool(config.mock_llm or os.getenv("MOCK_LLM", "0") == "1")
        self.api_url = os.getenv("LLM_API_URL", "")
        self.api_key = os.getenv("LLM_API_KEY", "")

    async def call_json(self, prompt: str, fixture_name: str | None = None) -> dict[str, Any]:
        async with self._semaphore:
            self.call_count += 1
            last_error: Exception | None = None
            for attempt in range(self.config.retry_attempts):
                try:
                    raw = await self._call_once(prompt, fixture_name=fixture_name, retry_prompt=(attempt > 0))
                    parsed = self._parse_json(raw)
                    if parsed is not None:
                        return parsed
                    if attempt == 0:
                        prompt = prompt + "\nReturn raw JSON only."
                        continue
                    return {"_error": "LLMParseError", "raw": raw}
                except Exception as exc:  # pragma: no cover - network path
                    last_error = exc
                    if attempt + 1 >= self.config.retry_attempts:
                        raise
                    await asyncio.sleep(self.config.retry_backoff_seconds * (2 ** attempt))
            if last_error is not None:
                raise last_error
            raise RuntimeError("LLM call failed")

    async def _call_once(self, prompt: str, fixture_name: str | None = None, retry_prompt: bool = False) -> str:
        if self.mock_llm:
            if fixture_name:
                fixture_path = Path(self.config.fixtures_root) / fixture_name
                if fixture_path.exists():
                    return fixture_path.read_text(encoding="utf-8")
            return json.dumps({"mock": True})

        if not self.api_url:
            return json.dumps({"mock": True, "prompt_preview": prompt[:200]})

        payload = json.dumps(
            {
                "model": self.config.model_name,
                "input": prompt,
            }
        ).encode("utf-8")
        req = request.Request(self.api_url, data=payload, headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        def run_request() -> str:
            with request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
                return body

        return await asyncio.to_thread(run_request)

    def _parse_json(self, raw: str) -> dict[str, Any] | None:
        stripped = _strip_fences(raw)
        try:
            result = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(result, dict):
            return result
        return {"result": result}


def run_async(coro):
    return asyncio.run(coro)


def maybe_flag_parse_error(raw_response: str, clause_id: str, obligation_id: str | None = None) -> dict[str, Any]:
    return {
        "type": "LLMParseError",
        "clause_id_normalized": clause_id,
        "obligation_id": obligation_id,
        "severity": "Medium",
        "citation": {"doc_id": "", "start_char": 0, "end_char": 0, "quote": ""},
        "summary": raw_response[:500],
        "confidence": 0.0,
    }
