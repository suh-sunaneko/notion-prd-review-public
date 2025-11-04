from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from .runner import PipelineError, PipelineResult, run_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="notion-formatter",
        description="Format a Notion requirement document and append AI review results.",
    )
    parser.add_argument(
        "--page-id",
        default=os.getenv("NOTION_TARGET_PAGE_ID"),
        help="Target Notion page ID to update (defaults to env NOTION_TARGET_PAGE_ID).",
    )
    parser.add_argument(
        "--template-page-id",
        default=os.getenv("NOTION_TEMPLATE_PAGE_ID"),
        help="Template Notion page ID (defaults to env NOTION_TEMPLATE_PAGE_ID).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the result as JSON (for GitHub Actions consumption).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        result = run_pipeline(
            page_id=args.page_id or "",
            template_page_id=args.template_page_id or "",
        )
    except PipelineError as exc:
        print(f"[notion-formatter] ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net for unexpected errors
        print(f"[notion-formatter] UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload: Dict[str, Any] = {
            "page_id": result.page_id,
            "template_page_id": result.template_page_id,
            "review_page_id": result.review_page_id,
            "is_complete": result.is_complete,
            "completion_message": result.completion_message,
            "updated_block_count": result.block_count,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        status = "完了" if result.is_complete else "要追記"
        review_info = (
            f" review={result.review_page_id}"
            if result.review_page_id
            else ""
        )
        print(
            (
                f"[notion-formatter] 更新完了: page={result.page_id}"
                f"{review_info} "
                f"blocks={result.block_count} status={status} "
                f"message={result.completion_message}"
            )
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
