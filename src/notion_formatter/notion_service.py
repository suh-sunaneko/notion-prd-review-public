from __future__ import annotations

from typing import Dict, Iterable, List, Set

from notion_client import Client

RichText = List[Dict[str, object]]
Block = Dict[str, object]

PRESERVE_LEADING_BLOCKS = 1


def extract_plain_text(rich_text: Iterable[Dict[str, object]]) -> str:
    return "".join(fragment.get("plain_text", "") for fragment in rich_text)


class NotionService:
    """Wraps the Notion SDK with helpers tailored to the formatting workflow."""

    def __init__(self, api_key: str) -> None:
        self._client = Client(auth=api_key)

    def fetch_page_markdown(self, page_id: str) -> str:
        blocks = self._fetch_block_children(page_id)
        lines: List[str] = []
        self._blocks_to_markdown(blocks, lines, 0)
        return "\n".join(lines).strip()

    def replace_page_content(self, page_id: str, blocks: List[Block]) -> None:
        self._archive_existing_children(page_id)
        blocks_to_append = list(blocks)
        for chunk_start in range(0, len(blocks_to_append), 50):
            chunk = blocks_to_append[chunk_start : chunk_start + 50]
            if not chunk:
                continue
            self._client.blocks.children.append(
                block_id=page_id,
                children=chunk,
            )

    def update_status_property(
        self,
        page_id: str,
        property_name: str,
        option_name: str,
    ) -> None:
        if not property_name:
            raise ValueError("property_name must be a non-empty string")
        if not option_name:
            raise ValueError("option_name must be a non-empty string")

        self._client.pages.update(
            page_id=page_id,
            properties={
                property_name: {"status": {"name": option_name}},
            },
        )

    def _archive_existing_children(self, block_id: str) -> None:
        children = self._fetch_block_children(block_id)
        seen: Set[str] = set()
        for index, child in enumerate(children):
            preserve = index < PRESERVE_LEADING_BLOCKS or self._should_preserve_block(
                child, seen=seen
            )
            if preserve:
                continue
            block_id_value = child.get("id")
            if isinstance(block_id_value, str):
                self._client.blocks.update(block_id=block_id_value, archived=True)

    def _should_preserve_block(self, block: Block, *, seen: Set[str]) -> bool:
        preserved_types = {"button", "template_button"}
        preserved_keys = {"button", "template_button"}

        block_type = str(block.get("type"))
        if block_type in preserved_types:
            return True

        if any(key in block for key in preserved_keys):
            return True

        if block_type == "callout":
            callout = block.get("callout", {})
            rich_text = callout.get("rich_text", [])
            text = extract_plain_text(rich_text)
            if "解決したい課題" in text or "要件定義レビュー" in text:
                return True

        block_id = block.get("id")
        if not isinstance(block_id, str):
            block_id = None

        if block_id and block_id in seen:
            return False

        if block.get("has_children") and block_id:
            seen.add(block_id)
            descendants = self._fetch_block_children(block_id)
            for child in descendants:
                if self._should_preserve_block(child, seen=seen):
                    return True

        return False

    def _fetch_block_children(self, block_id: str) -> List[Block]:
        results: List[Block] = []
        cursor: str | None = None
        while True:
            response = self._client.blocks.children.list(
                block_id=block_id,
                start_cursor=cursor,
                page_size=100,
            )
            batch = response.get("results", [])
            results.extend(batch)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return results

    def _blocks_to_markdown(
        self, blocks: Iterable[Block], output: List[str], indent: int
    ) -> None:
        indent_str = "  " * indent
        for block in blocks:
            block_type = block.get("type")
            data = block.get(block_type, {})
            rich_text = data.get("rich_text", [])
            content = extract_plain_text(rich_text).strip()

            if block_type in {"paragraph", "quote"}:
                if content:
                    prefix = "> " if block_type == "quote" else ""
                    output.append(f"{indent_str}{prefix}{content}")
            elif block_type in {"heading_1", "heading_2", "heading_3"}:
                level = int(block_type[-1])
                output.append(f"{indent_str}{'#' * level} {content}")
            elif block_type == "bulleted_list_item":
                output.append(f"{indent_str}- {content}")
            elif block_type == "numbered_list_item":
                output.append(f"{indent_str}1. {content}")
            elif block_type == "to_do":
                checked = data.get("checked", False)
                checkbox = "x" if checked else " "
                output.append(f"{indent_str}- [{checkbox}] {content}")
            elif block_type == "callout":
                output.append(f"{indent_str}💡 {content}")
            elif block_type == "code":
                language = data.get("language", "plain text")
                output.append(f"{indent_str}```{language}")
                output.append(content)
                output.append(f"{indent_str}```")
            elif block_type == "divider":
                output.append(f"{indent_str}---")

            if block.get("has_children"):
                children = self._fetch_block_children(block["id"])
                self._blocks_to_markdown(children, output, indent + 1)
