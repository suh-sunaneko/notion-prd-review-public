from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPayload:
    system_prompt: str
    user_prompt: str


def build_prompts(
    *,
    template_markdown: str,
    page_markdown: str,
    review_guidelines: str | None,
    review_section_heading: str,
    completion_phrase: str,
) -> PromptPayload:
    system_prompt = (
        "You are an assistant that reformats requirement definition documents for a sales team.\n"
        "Follow the template strictly, keep terminology in Japanese when provided, and make it easy to read.\n"
        "Perform two tasks:\n"
        "1. Rewrite the draft so it aligns with the template structure and headings.\n"
        f"2. Provide an AI review section called '{review_section_heading}' that highlights missing, improvable, and confirmed information.\n"
        "Use concise, direct Japanese. Preserve critical data points, tables, and bullet structures.\n"
        "Always return valid JSON matching the schema described in the user message."
    )

    review_block = (
        f"\n## レビュー観点ガイドライン\n{review_guidelines.strip()}"
        if review_guidelines and review_guidelines.strip()
        else ""
    )

    user_prompt = f"""
あなたは営業担当者が作成した粗い要件定義ドラフトを整形し、レビュー観点から不足情報を洗い出すAIです。

## 出力要件
- JSONオブジェクトを返却してください。
- プロパティ定義:
  - formatted_markdown: string
    - Markdown形式。テンプレート構造に合わせて整形した本文と、末尾にAIレビューセクションを含める。
    - レビューパートでは以下の順番の小見出しを含めること:
      1. ❌ 不足している項目
      2. ⚠️ 改善が必要な項目
      3. ✅ 適切に記載されている項目
      4. 🎉 完璧です (不足なしの場合のみ1行で記載)
    - ページ冒頭の自由記述（営業担当者が入力した要望）を起点に、テンプレートの各セクションへ可能な限り具体的に落とし込むこと。
    - 既存の案内コールアウト（"解決したい課題を自由に…"）はそのままにし、同じ内容のコールアウトを追加生成しないこと。
    - 各主要セクションで内容が不足している場合は、本文や箇条書きの直後に "`- 未記入。🔴 レビュー: 質問文（例: 選択肢A / 選択肢B / 選択肢C）`" の形式で追記し、`🔴` を含む赤文字の質問と 2～3 個の例示案を提示すること。
      - 例: `- 未記入。🔴 レビュー: ペルソナを誰に設定しますか？（例: 営業担当 / カスタマーサクセス / PM）`
    - 既に情報がある場合でも補足が必要なら、既存の記述を残しつつ次行に `🔴 レビュー: ...` を追加して改善案を示すこと。
    - ❌ もしくは ⚠️ の項目が1つでもある場合は、`🎉 完璧です` セクションを出力しないこと。
    - 各レビューヘッダーの下に内容がない場合は、そのヘッダーごと省略すること。
  - completion_summary: object
    - is_complete: boolean
    - status_message: string (例: "{completion_phrase}" または改善が必要な理由)

## フォーマット基準（テンプレート）
{template_markdown}

{review_block}

## 現在のドラフト
{page_markdown}

ドラフトがテンプレートに対して不足している場合でも、分かっている情報は必ず残し、足りない情報はレビューセクションで補足してください。
"""

    return PromptPayload(system_prompt=system_prompt, user_prompt=user_prompt.strip())
