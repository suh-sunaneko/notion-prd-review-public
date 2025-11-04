from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from openai import OpenAI
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from .config import Settings
from .prompt_builder import PromptPayload


class AIServiceError(RuntimeError):
    """Raised when the AI service fails to return a valid response."""


@dataclass(frozen=True)
class AIResult:
    formatted_markdown: str
    is_complete: bool
    completion_message: str


class AIFormatter:
    """Handles interactions with the OpenAI API and enforces response structure."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._retry_limit = settings.retry_limit

    def generate(self, prompts: PromptPayload) -> AIResult:
        try:
            response_json = self._invoke_model(prompts)
        except RetryError as exc:
            raise AIServiceError("OpenAI API retry attempts exhausted.") from exc

        if "formatted_markdown" not in response_json:
            raise AIServiceError("Missing 'formatted_markdown' in AI response.")
        if "completion_summary" not in response_json:
            raise AIServiceError("Missing 'completion_summary' in AI response.")

        summary = response_json["completion_summary"]
        if not isinstance(summary, dict):
            raise AIServiceError("'completion_summary' must be an object.")

        formatted_markdown = str(response_json["formatted_markdown"]).strip()
        is_complete = bool(summary.get("is_complete"))
        completion_message = str(summary.get("status_message", "")).strip()

        return AIResult(
            formatted_markdown=formatted_markdown,
            is_complete=is_complete,
            completion_message=completion_message,
        )

    def _invoke_model(self, prompts: PromptPayload) -> Dict[str, Any]:
        @retry(
            stop=stop_after_attempt(self._retry_limit),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            reraise=True,
        )
        def call_api() -> Dict[str, Any]:
            completion = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompts.system_prompt},
                    {"role": "user", "content": prompts.user_prompt},
                ],
            )

            content = completion.choices[0].message.content
            if not content:
                raise AIServiceError("Received empty response from OpenAI.")

            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise AIServiceError("Failed to parse JSON from OpenAI response.") from exc

        return call_api()
