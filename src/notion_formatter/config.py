from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency safeguard
    load_dotenv = None

if load_dotenv:
    load_dotenv()


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    notion_api_key: str
    notion_template_page_id: str
    notion_review_page_id: Optional[str]
    openai_api_key: str
    openai_model: str
    review_section_heading: str
    completion_success_phrase: str
    retry_limit: int
    review_status_property_name: Optional[str]
    review_status_complete_value: str
    review_status_rejected_value: str


def load_settings() -> Settings:
    """Load configuration from environment variables with sensible defaults."""

    notion_api_key = os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        raise ConfigurationError("Environment variable NOTION_API_KEY is required.")

    template_page_id = os.getenv("NOTION_TEMPLATE_PAGE_ID")
    if not template_page_id:
        raise ConfigurationError("Environment variable NOTION_TEMPLATE_PAGE_ID is required.")

    review_page_id = os.getenv("NOTION_REVIEW_PAGE_ID")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ConfigurationError("Environment variable OPENAI_API_KEY is required.")

    openai_model = "gpt-4o-mini"
    review_section_heading = "AIレビュー結果"
    completion_success_phrase = "🎉 完璧です"

    retry_env = os.getenv("RETRY_LIMIT", "3")
    try:
        retry_limit = max(1, int(retry_env))
    except ValueError as exc:
        raise ConfigurationError(
            "Environment variable RETRY_LIMIT must be an integer."
        ) from exc

    review_status_property_name = os.getenv(
        "NOTION_REVIEW_STATUS_PROPERTY",
        "レビュー状況",
    )
    if review_status_property_name is not None:
        review_status_property_name = review_status_property_name.strip() or None

    review_status_complete_value = os.getenv(
        "NOTION_REVIEW_STATUS_COMPLETE_VALUE",
        "完了",
    ).strip()
    review_status_rejected_value = os.getenv(
        "NOTION_REVIEW_STATUS_REJECTED_VALUE",
        "差し戻し",
    ).strip()

    return Settings(
        notion_api_key=notion_api_key,
        notion_template_page_id=template_page_id,
        notion_review_page_id=review_page_id,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        review_section_heading=review_section_heading,
        completion_success_phrase=completion_success_phrase,
        retry_limit=retry_limit,
        review_status_property_name=review_status_property_name,
        review_status_complete_value=review_status_complete_value,
        review_status_rejected_value=review_status_rejected_value,
    )
