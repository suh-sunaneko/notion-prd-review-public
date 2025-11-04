from __future__ import annotations

from dataclasses import dataclass

from .ai_client import AIFormatter, AIResult
from .config import ConfigurationError, Settings, load_settings
from .markdown_converter import markdown_to_blocks
from .notion_service import NotionService
from .prompt_builder import build_prompts


@dataclass(frozen=True)
class PipelineResult:
    page_id: str
    template_page_id: str
    review_page_id: str | None
    is_complete: bool
    completion_message: str
    block_count: int


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot complete successfully."""


def run_pipeline(page_id: str, template_page_id: str | None = None) -> PipelineResult:
    if not page_id:
        raise PipelineError("Target Notion page ID is required.")

    try:
        settings: Settings = load_settings()
    except ConfigurationError as exc:
        raise PipelineError(str(exc)) from exc

    template_id = template_page_id or settings.notion_template_page_id
    if not template_id:
        raise PipelineError("Template Notion page ID is required.")

    notion = NotionService(settings.notion_api_key)
    template_markdown = notion.fetch_page_markdown(template_id)
    draft_markdown = notion.fetch_page_markdown(page_id)
    review_markdown = None
    if settings.notion_review_page_id:
        review_markdown = notion.fetch_page_markdown(settings.notion_review_page_id)

    prompts = build_prompts(
        template_markdown=template_markdown,
        page_markdown=draft_markdown,
        review_guidelines=review_markdown,
        review_section_heading=settings.review_section_heading,
        completion_phrase=settings.completion_success_phrase,
    )

    ai_formatter = AIFormatter(settings)
    ai_result: AIResult = ai_formatter.generate(prompts)

    page_blocks = markdown_to_blocks(
        ai_result.formatted_markdown,
        review_heading=settings.review_section_heading,
        is_complete=ai_result.is_complete,
    )
    if not page_blocks:
        raise PipelineError("AI returned empty document; refusing to overwrite the page.")

    notion.replace_page_content(page_id, page_blocks)

    status_property = settings.review_status_property_name
    complete_value = settings.review_status_complete_value
    rejected_value = settings.review_status_rejected_value
    if status_property and complete_value and rejected_value:
        target_status = complete_value if ai_result.is_complete else rejected_value
        notion.update_status_property(page_id, status_property, target_status)

    return PipelineResult(
        page_id=page_id,
        template_page_id=template_id,
        review_page_id=settings.notion_review_page_id,
        is_complete=ai_result.is_complete,
        completion_message=ai_result.completion_message,
        block_count=len(page_blocks),
    )
