from __future__ import annotations

import os
import re
from typing import Dict, List

Block = Dict[str, object]

INSTRUCTION_CALLOUT_TEXT = "解決したい課題を自由に以下に記述して、「要件定義レビュー」ボタンを押下してください"


def make_rich_text(text: str, *, color: str | None = None) -> List[Dict[str, object]]:
    annotations = {
        "bold": False,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": color or "default",
    }
    return [
        {
            "type": "text",
            "text": {"content": text},
            "annotations": annotations,
        }
    ]


def _extract_text(block: Block) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""
    data = block.get(block_type)
    if not isinstance(data, dict):
        return ""
    rich_text = data.get("rich_text", [])
    fragments: List[str] = []
    for fragment in rich_text:
        if not isinstance(fragment, dict):
            continue
        if "plain_text" in fragment:
            fragments.append(str(fragment.get("plain_text", "")))
            continue
        text_data = fragment.get("text")
        if isinstance(text_data, dict):
            fragments.append(str(text_data.get("content", "")))
    return "".join(fragments).strip()


def _block_has_content(block: Block) -> bool:
    block_type = block.get("type")
    if not block_type:
        return False
    if block_type == "divider":
        return False
    if block_type == "code":
        code_data = block.get("code")
        if not isinstance(code_data, dict):
            return False
        return bool(_extract_text(block))
    if block_type == "to_do":
        todo = block.get("to_do")
        if not isinstance(todo, dict):
            return False
        return bool(_extract_text(block))
    if block_type in {
        "paragraph",
        "quote",
        "callout",
        "bulleted_list_item",
        "numbered_list_item",
    }:
        return bool(_extract_text(block))
    return True


def _is_instruction_callout(block: Block) -> bool:
    if block.get("type") != "callout":
        return False
    text = _extract_text(block)
    return INSTRUCTION_CALLOUT_TEXT in text


def _prune_review_sections(
    blocks: List[Block],
    review_heading: str,
    is_complete: bool | None,
    debug_enabled: bool,
) -> List[Block]:
    pruned: List[Block] = []
    idx = 0
    while idx < len(blocks):
        block = blocks[idx]
        block_type = block.get("type")
        if block_type == "heading_2" and _extract_text(block) == review_heading:
            pruned.append(block)
            idx += 1
            while idx < len(blocks):
                candidate = blocks[idx]
                candidate_type = candidate.get("type")
                if candidate_type == "heading_2":
                    break
                if candidate_type == "heading_3":
                    title = _extract_text(candidate)
                    subsection: List[Block] = []
                    cursor = idx + 1
                    while cursor < len(blocks):
                        follower = blocks[cursor]
                        follower_type = follower.get("type")
                        if follower_type in {"heading_3", "heading_2"}:
                            break
                        subsection.append(follower)
                        cursor += 1

                    has_content = any(_block_has_content(item) for item in subsection)
                    keep = has_content
                    if title == "🎉 完璧です":
                        if is_complete is None:
                            keep = has_content
                        else:
                            keep = is_complete
                    if keep:
                        pruned.append(candidate)
                        pruned.extend(subsection)
                    elif debug_enabled:
                        print(
                            "DEBUG: Dropping review subsection",
                            {
                                "title": title,
                                "has_content": has_content,
                                "is_complete": is_complete,
                            },
                        )
                    idx = cursor
                    continue

                pruned.append(candidate)
                idx += 1
            continue

        pruned.append(block)
        idx += 1

    return pruned


def markdown_to_blocks(
    markdown: str,
    *,
    review_heading: str = "AIレビュー結果",
    is_complete: bool | None = None,
) -> List[Block]:
    blocks: List[Block] = []
    paragraph_buffer: List[str] = []
    in_code = False
    code_language = "plain text"
    code_lines: List[str] = []
    current_heading_level_2: str | None = None
    current_heading_level_3: str | None = None

    def determine_text_color(text: str | None = None) -> str | None:
        if text:
            stripped = text.strip()
            if "🔴" in stripped or stripped.startswith("【レビュー】"):
                return "red"
        if (
            current_heading_level_2 == review_heading
            and current_heading_level_3 in {"❌ 不足している項目", "⚠️ 改善が必要な項目"}
        ):
            return "red"
        return None

    def flush_paragraph() -> None:
        nonlocal paragraph_buffer
        if not paragraph_buffer:
            return
        text = " ".join(paragraph_buffer).strip()
        paragraph_buffer.clear()
        if not text:
            return
        # 空のテキストや空白のみのテキストをスキップ
        if not text or text.isspace():
            return
        color = determine_text_color(text)
        blocks.append(
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": make_rich_text(text, color=color),
                },
            }
        )

    def flush_code_block() -> None:
        nonlocal in_code, code_language, code_lines
        if not in_code:
            return
        code_text = "\n".join(code_lines)
        # 空のコードブロックをスキップ
        if not code_text.strip():
            in_code = False
            code_language = "plain text"
            code_lines = []
            return
        blocks.append(
            {
                "type": "code",
                "code": {
                    "language": code_language or "plain text",
                    "rich_text": make_rich_text(code_text),
                },
            }
        )
        in_code = False
        code_language = "plain text"
        code_lines = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_code:
                flush_code_block()
                continue
            flush_paragraph()
            in_code = True
            code_language = line[3:].strip() or "plain text"
            code_lines = []
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        if not line.strip():
            flush_paragraph()
            continue

        if line.startswith("#"):
            flush_paragraph()
            level = len(line) - len(line.lstrip("#"))
            content = line[level:].strip()
            if not content:  # 空の見出しをスキップ
                continue
            level = min(max(level, 1), 3)
            key = f"heading_{level}"
            blocks.append(
                {
                    "type": key,
                    key: {"rich_text": make_rich_text(content)},
                }
            )
            if level == 1:
                current_heading_level_2 = None
                current_heading_level_3 = None
            elif level == 2:
                current_heading_level_2 = content
                current_heading_level_3 = None
            else:
                current_heading_level_3 = content
            continue

        if line.startswith(">"):
            flush_paragraph()
            content = line[1:].strip()
            if not content:  # 空の引用をスキップ
                continue
            blocks.append(
                {
                    "type": "quote",
                    "quote": {"rich_text": make_rich_text(content, color=determine_text_color(content))},
                }
            )
            continue

        if line.startswith("---"):
            flush_paragraph()
            blocks.append({
                "type": "divider",
                "divider": {}
            })
            continue

        if line.startswith("- [") and "]" in line:
            flush_paragraph()
            closing = line.index("]")
            marker = line[3:closing].strip().lower()
            checked = marker in {"x", "✓", "done"}
            content = line[closing + 1 :].strip()
            if not content:  # 空のToDoをスキップ
                continue
            blocks.append(
                {
                    "type": "to_do",
                    "to_do": {
                        "checked": checked,
                        "rich_text": make_rich_text(content, color=determine_text_color(content)),
                    },
                }
            )
            continue

        if line.startswith("- "):
            flush_paragraph()
            content = line[2:].strip()
            if not content:  # 空の箇条書きをスキップ
                continue
            blocks.append(
                {
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": make_rich_text(content, color=determine_text_color(content)),
                    },
                }
            )
            continue

        if re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            content = re.sub(r"^\d+\.\s+", "", line).strip()
            if not content:  # 空の番号付きリストをスキップ
                continue
            blocks.append(
                {
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": make_rich_text(content, color=determine_text_color(content)),
                    },
                }
            )
            continue

        if line.startswith("💡"):
            flush_paragraph()
            content = line[1:].strip()
            if not content:  # 空のコールアウトをスキップ
                continue
            blocks.append(
                {
                    "type": "callout",
                    "callout": {
                        "icon": {"type": "emoji", "emoji": "💡"},
                        "rich_text": make_rich_text(content, color=determine_text_color(content)),
                    },
                }
            )
            continue

        paragraph_buffer.append(line)

    flush_paragraph()
    flush_code_block()
    
    # デバッグ用：ブロック構造を検証（環境変数で制御）
    debug_enabled = os.getenv("DEBUG_MARKDOWN_CONVERTER", "false").lower() == "true"
    if debug_enabled:
        print(f"DEBUG: Generated {len(blocks)} blocks")
        for i, block in enumerate(blocks):
            print(f"DEBUG: Block {i}: {block}")
            if not block.get("type"):
                print(f"ERROR: Block {i} has no type: {block}")
            else:
                block_type = block["type"]
                # dividerブロックは特別な処理（空のオブジェクトが有効）
                if block_type == "divider":
                    if block_type not in block:
                        print(f"ERROR: Block {i} ({block_type}) has no data: {block}")
                else:
                    if not block.get(block_type):
                        print(f"ERROR: Block {i} ({block_type}) has no data: {block}")
    
    # 空のブロックをフィルタリング
    valid_blocks = []
    for i, block in enumerate(blocks):
        if not block.get("type"):
            if debug_enabled:
                print(f"WARNING: Skipping block {i} with no type: {block}")
            continue
        block_type = block["type"]
        
        # dividerブロックは特別な処理（空のオブジェクトが有効）
        if block_type == "divider":
            if block_type not in block:
                if debug_enabled:
                    print(f"WARNING: Skipping block {i} ({block_type}) with no data: {block}")
                continue
        else:
            # その他のブロックタイプはデータが必要
            if not block.get(block_type):
                if debug_enabled:
                    print(f"WARNING: Skipping block {i} ({block_type}) with no data: {block}")
                continue
        
        valid_blocks.append(block)
    
    pruned_blocks = _prune_review_sections(
        valid_blocks,
        review_heading=review_heading,
        is_complete=is_complete,
        debug_enabled=debug_enabled,
    )

    filtered_blocks = [
        block for block in pruned_blocks if not _is_instruction_callout(block)
    ]

    if debug_enabled:
        print(f"DEBUG: Filtered to {len(valid_blocks)} valid blocks")
        print(f"DEBUG: Pruned to {len(pruned_blocks)} blocks after review cleanup")
        print(f"DEBUG: Removed {len(pruned_blocks) - len(filtered_blocks)} instruction callouts")
    return filtered_blocks
