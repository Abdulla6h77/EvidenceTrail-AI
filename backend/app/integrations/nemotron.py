from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings


class ModelUnavailableError(RuntimeError):
    pass


class NemotronAdapter:
    """Configurable OpenAI-compatible adapter for NVIDIA Nemotron."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_usage: dict[str, int | float | bool] | None = None
        self.last_response_metadata: dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return bool(self.settings.model_api_key and self.settings.nemotron_model)

    def status(self) -> dict[str, str]:
        if not self.configured:
            return {"status": "not_configured", "detail": "MODEL_API_KEY and NEMOTRON_MODEL are required"}
        return {"status": "ready", "detail": f"Configured for {self.settings.nemotron_model}"}

    async def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: type[BaseModel],
        retries: int = 2,
    ) -> BaseModel:
        if not self.configured:
            raise ModelUnavailableError("NVIDIA Nemotron is not configured")
        self.last_usage = None
        self.last_response_metadata = {}
        url = f"{self.settings.model_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.model_api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.settings.nemotron_model,
            "temperature": 0,
            "max_tokens": 8192,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if "openrouter.ai" in self.settings.model_base_url:
            body["reasoning"] = {"enabled": False}
        last_error: Exception | None = None
        validation_detail = ""
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=body)
                    response.raise_for_status()
                    payload = response.json()
                usage = payload.get("usage")
                if isinstance(usage, dict):
                    self.last_usage = {
                        str(key): value
                        for key, value in usage.items()
                        if isinstance(value, (int, float))
                    }
                content = payload["choices"][0]["message"]["content"]
                if isinstance(content, str):
                    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
                    content = json.loads(content)
                validated = output_model.model_validate(content)
                from urllib.parse import urlsplit
                self.last_response_metadata = {
                    "requested_model": self.settings.nemotron_model,
                    "returned_model": payload.get("model"),
                    "response_id": payload.get("id"),
                    "provider": payload.get("provider"),
                    "endpoint_host": urlsplit(self.settings.model_base_url).hostname,
                }
                return validated
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                last_error = exc
                if isinstance(exc, ValidationError):
                    validation_detail = "; " + ", ".join(
                        f"{'.'.join(map(str, error['loc']))}: {error['type']}" for error in exc.errors()
                    )
                elif isinstance(exc, httpx.HTTPStatusError):
                    validation_detail = f"; HTTP {exc.response.status_code}"
                if isinstance(exc, ValidationError) and isinstance(payload, dict):
                    choice = (payload.get("choices") or [{}])[0]
                    validation_detail += f"; finish_reason={choice.get('finish_reason')}; content_type={type(content).__name__}"
                if attempt < retries:
                    await asyncio.sleep(2**attempt)
        raise ModelUnavailableError(f"Nemotron structured completion failed: {type(last_error).__name__}{validation_detail}") from last_error
