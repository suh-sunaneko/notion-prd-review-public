# Notion 要件定義 自動フォーマット化ワークフロー

営業担当者が作成した粗い要件定義ページを、テンプレートに沿って自動整形し、不足情報をAIレビューで洗い出す仕組みです。Notionボタンからの1クリック実行を前提に、GitHub Actions・Notion API・OpenAI APIを連携させています。

## 機能概要
- Notionページとテンプレートページを取得し、テンプレート構造に沿ってMarkdownへ再整形
- OpenAIによるレビュー結果（不足情報・改善ポイント・適切な点・完璧判定）を同じページへ追記
- 既存ブロックをアーカイブして整形済みブロックへ置き換え
- レビュー完了時に`レビュー状況`プロパティを自動更新（完了時: `完了`、要追記時: `差し戻し`）
- 完璧判定メッセージ（例: `🎉 完璧です`）をGitHub Actionsサマリから確認可能

## セットアップ
1. **リポジトリの準備**  
   テンプレートリポジトリをForkし、GitHub Actionsを有効化します。
2. **Python環境**  
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install .
   ```
3. **環境変数 (Secrets管理前提)**  
   `python-dotenv` による `.env` 読み込み機能はありますが、本運用ではすべてGitHub Secretsで管理してください。
   - `NOTION_API_KEY`
   - `OPENAI_API_KEY`
   - `NOTION_TEMPLATE_PAGE_ID`
   - `NOTION_REVIEW_PAGE_ID`
   
   **オプション環境変数（デフォルト値あり）**：
   - `NOTION_REVIEW_STATUS_PROPERTY`: レビュー状況プロパティ名（デフォルト: `レビュー状況`）
   - `NOTION_REVIEW_STATUS_COMPLETE_VALUE`: 完了時に設定する値（デフォルト: `完了`）
   - `NOTION_REVIEW_STATUS_REJECTED_VALUE`: 差し戻し時に設定する値（デフォルト: `差し戻し`）
   - `RETRY_LIMIT`: OpenAI API呼び出しのリトライ上限（デフォルト: `3`）
   
   **固定値（コード内にハードコード）**：
   - `OPENAI_MODEL`: `gpt-4o-mini`
   - `REVIEW_SECTION_HEADING`: `AIレビュー結果`
   - `COMPLETION_SUCCESS_PHRASE`: `🎉 完璧です`
4. **Notion設定**  
   - テンプレートページを作成（レビュー観点は別ページで管理）
   - 要件ページをデータベース化し、`レビュー状況`（ステータス）プロパティを追加
     - プロパティ名: `レビュー状況`（または`NOTION_REVIEW_STATUS_PROPERTY`で指定した値）
     - タイプ: ステータス
     - 選択肢（推奨）:
       - `差し戻し`（デフォルトの差し戻し値）
       - `未着手`
       - `未対応`
       - グループ「進行中」:
         - `差し戻し`
         - `レビュー中`
       - グループ「完了」:
         - `完了`（デフォルトの完了値）
   - レビュー用ボタンはプロパティ更新のみ行い、Webhook送信はデータベースオートメーション経由とする（ページボタン単体ではカスタムJSONが送信できないため）[*](https://www.notion.com/ja/help/webhook-actions)
   - **重要**: GitHubリポジトリにある `templates/notion_requirement_template.md` と `templates/notion_review_checklist.md` はあくまで**サンプル**です。これらの内容を参考に、**Notion上で実際のページを作成**する必要があります。詳細は「非エンジニア向けガイド」の「4. Notionページの作成」を参照してください。
5. **GitHub Secrets**  
   - `NOTION_API_KEY`, `OPENAI_API_KEY`, `NOTION_TEMPLATE_PAGE_ID`, `NOTION_REVIEW_PAGE_ID` をSecretsに登録

## GitHub Actions での実行
ワークフロー: `.github/workflows/notion-auto-format.yml`

### 手動トリガー
Actionsタブから `Run workflow` を押し、`page_id`（整形したいNotionページID）のみ入力してください。テンプレートIDは環境変数から読み込みます。

### Webhookトリガー
Notionボタンや外部システムから以下のようなリクエストを送信します（ボタンを押したページのIDがそのまま `page_id` になります）。
```bash
curl -X POST \
  -H "Authorization: token <GITHUB_TOKEN>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/<owner>/<repo>/dispatches \
  -d '{
    "event_type": "notion-auto-format",
    "client_payload": {
      "page_id": "xxxxxxxxxxxxxxxxxxxx"
    }
  }'
```

## 開発メモ
- Notion APIの制約により、既存ブロックはアーカイブ→整形済みブロックを追加する方式
- Markdown変換は見出し / 箇条書き / チェックリスト / 引用 / コード / 区切り線 / コールアウトに対応
- OpenAIレスポンスはJSONスキーマを強制し、整形結果が空の場合は書き換えを中断
- レビュー完了/差し戻し時に`レビュー状況`プロパティを自動更新（環境変数でプロパティ名・値をカスタマイズ可能）
- リトライ上限 (`RETRY_LIMIT`) や完璧判定メッセージは環境変数で調整可能
- ボタンや「解決したい課題」を含むコールアウトブロックは自動的に保持される

---

## 非エンジニア向けガイド

### 1. 準備するもの
- GitHubアカウント（自社リポジトリへアクセスできること）
- Notionワークスペースの編集権限
- OpenAI APIキー（管理者から共有されるもの）
- テンプレート用Notionページ / レビュー観点ページ（GitHubのサンプルMarkdownファイルを参考にNotionで作成）

### 2. 設定の全体像
1. GitHubに秘密情報（APIキーやページID）を登録する  
2. Notionでテンプレートページとレビュー観点ページを作り、ページIDを控える  
3. Notionの各要件ページに「自動整形ボタン」を配置する  
4. ボタンを押すとGitHub Actionsが動き、ページが整形・レビューされる  

下記を順に進めれば設定が完了します。専門的なコマンド操作は不要です。

### 3. GitHub Secrets の設定方法
1. GitHubで対象リポジトリを開きます。
2. `Settings` → `Secrets and variables` → `Actions` をクリックします。
3. `New repository secret` を押し、以下の名前と値を登録します。
   - `NOTION_API_KEY`: Notionの統合で発行したシークレットキー
   - `OPENAI_API_KEY`: OpenAIのAPIキー
   - `NOTION_TEMPLATE_PAGE_ID`: テンプレートページのID
   - `NOTION_REVIEW_PAGE_ID`: レビュー観点ページのID（オプション）
   
   **オプション設定**（必要に応じて追加）:
   - `NOTION_REVIEW_STATUS_PROPERTY`: レビュー状況プロパティ名（デフォルト: `レビュー状況`）
   - `NOTION_REVIEW_STATUS_COMPLETE_VALUE`: 完了時に設定する値（デフォルト: `完了`）
   - `NOTION_REVIEW_STATUS_REJECTED_VALUE`: 差し戻し時に設定する値（デフォルト: `差し戻し`）
   - `RETRY_LIMIT`: OpenAI API呼び出しのリトライ上限（デフォルト: `3`）
   
   **注意**: `OPENAI_MODEL`、`REVIEW_SECTION_HEADING`、`COMPLETION_SUCCESS_PHRASE`は固定値としてコード内にハードコードされているため、Secretsに登録する必要はありません。

> **ページIDの取得方法**  
> NotionページのURL末尾にある英数字（スラッグ形式の場合は最後の32文字）がページIDです。  
> 例）`https://www.notion.so/workspace/XXXXXXXXXXXXXXX?pvs=4` → `XXXXXXXXXXXXXXX`

### 4. Notionページの作成
**重要**: 本リポジトリの `templates/` ディレクトリにあるMarkdownファイル（`notion_requirement_template.md` と `notion_review_checklist.md`）は**サンプル**です。これらを参考に、**Notion上で実際のページを新規作成**してください。

1. **テンプレートページの作成**
   - Notionで新しいページを作成します。
   - GitHubリポジトリの `templates/notion_requirement_template.md` の内容を参考に、同様の構造でテンプレートページを整備します（内容をコピー＆ペーストするか、必要に応じてカスタマイズしてください）。
   - `{TBD: }` の書式で未定事項を管理できるようにしておくと便利です。
2. **レビュー観点ページの作成**
   - Notionで別の新しいページを作成します。
   - GitHubリポジトリの `templates/notion_review_checklist.md` の内容を参考に、レビュー観点ページを整備します（内容をコピー＆ペーストするか、必要に応じてカスタマイズしてください）。
   - このページはレビュワーと共有して、レビューの基準として使用します。
3. **ページIDの取得と登録**
   - 上記2ページのページIDをコピーし、GitHub Secretsに登録します（「3. GitHub Secrets の設定方法」を参照）。

### 5. Notionデータベース＆オートメーション設定
Notionボタン単体では任意のJSONや`{{pageId}}`の差し込みが行えないため、データベースオートメーションを利用してMakeへWebhookを送信します[*](https://www.notion.com/ja/help/webhook-actions)。

1. **データベースの用意**  
   - 要件ページをデータベースに変換し、最低限以下のプロパティを作成します。  
     - `案件名`（Title）  
     - `レビュー状況`（ステータス）：
       - 選択肢: `差し戻し`、`未着手`、`未対応`
       - グループ「進行中」: `差し戻し`、`レビュー中`
       - グループ「完了」: `完了`
       - デフォルト値は任意（ワークフロー実行時に自動更新されます）
     - その他必要なプロパティ（レコードIDはWebhookで自動送信されるため不要）  
     - 必要に応じて担当者や期日などの補助プロパティ
2. **要件定義レビューボタン**  
   - データベース右上の `+` → **ボタン** を追加し、アクションは「プロパティを更新」に設定。  
   - `レビュー状況` を `レビュー中` など任意の進行中ステータスに変更するよう構成します（Webhook送信はこの後のオートメーションで実施）。
3. **データベースオートメーション**  
   - データベース右上の「3点リーダ」→ **オートメーション** → **新しいオートメーションを追加**。  
   - トリガー：`レビュー状況` が `レビュー中` に変更されたとき（または任意のトリガー条件）。  
   - アクション：**Webhookを送信** を選び、以下の通り設定します。  
     | 項目 | 設定内容 | 補足 |
     | --- | --- | --- |
     | **URL** | `https://hook.make.com/<Makeで発行されたWebhook ID>` | MakeのカスタムWebhook URLを入力します。 |
     | **カスタムヘッダー** | `Content-Type` / `application/json` | Notion側では認証ヘッダーを付与できないため、後段のMakeで付与します。 |
     | **データベースプロパティ** | `案件名` など任意（`page_id`は選択不可） | 送信したいプロパティを選択します。レコードIDは自動で含まれます。 |
   - 保存後、オートメーションを有効化します。
4. **フィードバック反映**  
   - ワークフロー実行後、AIレビュー結果に基づいて`レビュー状況`が自動更新されます（完了時: `完了`、要追記時: `差し戻し`）。
   - 必要に応じて、別のオートメーションで`レビュー状況`を適切な値に戻すルールを設定できます。

### 6. Makeシナリオの設定
1. **シナリオを新規作成**  
   - Makeダッシュボードで「Create a new scenario」をクリックし、`Webhooks` → `Custom webhook` モジュールを追加します。  
   - 「Add」→名称を入力→「Save」でWebhook URLを発行し、`Copy address to clipboard`で控えます（Notionボタンの設定で使用）。
2. **ペイロードを受け取る**  
   - Webhookモジュールで「Run once」を押し、Notion側の「要件定義レビューボタン」を押してサンプルペイロードを取得します（`page_id` など選択したプロパティが含まれます）。
3. **GitHub REST APIを呼び出す**  
   - 次のモジュールに `HTTP` → `Make a request` を追加します。  
   - Method: `POST`  
   - URL: `https://api.github.com/repos/<GitHubユーザー名>/<リポジトリ名>/dispatches`（例：`https://api.github.com/repos/suh-sunaneko/notion-prd-review/dispatches`）  
   - Headers: `Authorization: token <GitHub PAT>`、`Accept: application/vnd.github+json`、`Content-Type: application/json`  
     - Body type: `Raw`, Content type: `application/json`, Request content:  
       ```json
       {
         "event_type": "notion-auto-format",
         "client_payload": {
           "page_id": "{{1.data.id}}"
         }
       }
       ```
       （`{{1.data.id}}` はWebhookモジュールで受信したページID。実際の受信データ構造に合わせて調整してください）
4. **トークン管理**  
   - GitHub PATはMakeのモジュール設定内で直接入力せず、`Connection`の「Add a connection」→`HTTP`→`Add a header`でセキュアに保存する運用を推奨します。  
   - PATのスコープは `repo` を必須とし、定期的に更新してください。
5. **シナリオを有効化**  
   - テスト実行でHTTP 204が返ることを確認後、「Schedule」をオンにして保存します。

以降はNotionボタンをクリックするとMakeがGitHub `repository_dispatch` を代理送信し、ワークフローが起動します。

### 7. 実行結果の見方
- GitHub Actionsが数分で完了し、同じページがテンプレート構造に整形されます。
- ページ末尾に `AIレビュー結果` セクションが追加されます。
  - ❌ 不足している項目：必須情報が抜けている箇所
  - ⚠️ 改善が必要な項目：情報はあるが質が足りない箇所
  - ✅ 適切に記載されている項目：十分に記載済みの箇所
  - 🎉 完璧です：全項目が揃ったタイミングで表示
- `レビュー状況`プロパティが自動更新されます：
  - 完璧な場合：`完了` に更新
  - 要追記がある場合：`差し戻し` に更新
- 再度ボタンを押すと最新状態を基に整形し直すため、指摘に対応したら再実行してください。

### 8. よくあるトラブルと対処
| 症状 | よくある原因 | 対処方法 |
| --- | --- | --- |
| Actionsが失敗する | Secretsが未設定、またはIDが誤っている | GitHubの `Actions` → 該当ジョブのログでエラー内容を確認し、Secretsを修正 |
| ページが更新されない | ボタンのWebhook設定が誤っている | Notionボタン設定を再確認（URL/トークン/ペイロードのJSON） |
| AIレビューが空になる | OpenAIの呼び出し上限・応答エラー | 一度時間を置き再実行。長文の場合はページを分けて対応 |
| 完了メッセージが出ない | ❌/⚠️が残っている | レビュー結果を確認し、該当箇所を追記 → ボタン再実行 |

---

## 用語メモ
- **ページID**：Notion各ページ固有の32桁ID。URLの末尾に表示される。
- **Secrets**：GitHub上で安全にAPIキーなどを保管する領域。リポジトリ設定から登録する。
- **GitHub Actions**：指定イベントをトリガーに自動処理を行う仕組み。本プロジェクトではNotionボタンから呼び出す。
- **repository_dispatch**：外部サービスからGitHub Actionsを起動するためのAPI。
- **AIレビュー結果**：仕上がった要件定義の不足・改善ポイントをまとめるセクション。営業セルフレビュー用。
