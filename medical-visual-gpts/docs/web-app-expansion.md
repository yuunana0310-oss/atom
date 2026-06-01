# Webアプリ化する場合の拡張案

## 基本方針

最初から本格的なWebアプリにせず、MarkdownとJSON Schemaで運用が回る状態を優先する。作例数、投稿案、更新履歴が増えてきた段階で、同じデータ構造を使ってWeb UIへ移行する。

## 最初に作るなら必要な画面

- GPT Instructions一覧
- GPT Instructions編集画面
- 作例一覧
- 作例詳細
- Threads投稿案一覧
- 投稿案詳細
- 更新履歴一覧
- 公開リスクチェック画面

## データモデル

最初は以下の3モデルで十分。

- `Example`: 医療ビジュアル作例
- `ThreadsPost`: Threads投稿案
- `GptVersionHistory`: GPT Instructions更新履歴

必要になったら以下を追加する。

- `GptProfile`: GPTごとの基本情報
- `KnowledgeFile`: 共通ナレッジ管理
- `Campaign`: 値上げ前、販売日、固定投稿更新などの販売施策
- `Asset`: 画像、サムネイル、作例リンク

## 技術構成案

### 最小

- Markdown
- JSON
- Google Sheets

### 軽量Web UI

- Next.js または Vite
- ローカルJSONまたはSQLite
- Markdownプレビュー
- JSON Schemaベースのフォーム

### 将来

- SQLite / PostgreSQL
- 作例画像アップロード
- Threads投稿案のステータス管理
- note販売ページ改善履歴
- 公開リスク表現の自動チェック

## 拡張しやすくするためのルール

- JSONのキーは英語のsnake_caseにする。
- Sheetsでは日本語見出しを使ってもよいが、内部キーとの対応表を残す。
- Markdown本文とメタデータを分ける。
- GPT Instructionsは公開用と自分用を分ける。
- 医療安全チェック項目は全GPTで共通化する。

## 優先しないもの

- 完全自動投稿
- 課金システム
- 複雑なユーザー管理
- 高度な分析ダッシュボード

まずは「作例が貯まる」「投稿導線が見える」「GPT更新履歴が残る」状態を優先する。
