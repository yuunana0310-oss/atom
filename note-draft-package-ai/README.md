# note-draft-package-ai

OpenAI APIを使って、note用の記事本文・画像・貼り付け用テキストをまとめて生成するローカルアプリです。

## できること

- note記事本文（Markdown）生成
- note貼り付け用テキスト生成
- タイトル候補生成
- アイキャッチ画像生成（gpt-image-1）
- 本文挿入用画像生成
- タグ候補生成
- 画像挿入位置メモ
- 記事パッケージのフォルダ保存

## できないこと（意図的）

- noteへの直接投稿
- note自動公開
- note公式API連携

公開操作は必ず人間が行ってください。

## セットアップ

```bash
# 1. .env を作成
cp .env.example .env
# .env の OPENAI_API_KEY を設定

# 2. 依存をインストール
pip install -r requirements.txt

# 3. 起動
streamlit run app.py
```

## モデル設定

`.env` の値を差し替えれば、コストや品質を調整できます。

| 用途 | デフォルト | 推奨用途 |
|------|------|------|
| TEXT_MODEL | gpt-5-mini | 量産記事・下書き |
| QUALITY_MODEL | gpt-5 | 販売導線・勝負記事 |
| IMAGE_MODEL | gpt-image-2 | 全画像（2026-04-21リリース、O系推論搭載・4K対応・日本語文字も従来比で安定） |

## 出力

```
outputs/
└─ 2026-05-10_記事テーマ/
   ├─ article.md
   ├─ note_paste.txt
   ├─ title_candidates.txt
   ├─ hashtags.txt
   ├─ image_insert_map.txt
   ├─ metadata.json
   └─ images/
      ├─ cover.png
      ├─ body_01.png
      └─ body_02.png
```

## 注意

医療・健康記事は、必ず人間が内容確認してから公開してください。AI生成は断定表現・誤情報の可能性があります。

## 開発フェーズ

- [x] Phase 1: テキスト生成・パッケージ保存
- [x] Phase 2: 画像付きパッケージ完成
- [ ] Phase 3: Threads告知文生成
- [ ] Phase 4: 品質管理・履歴管理
- [ ] Phase 5: Playwrightによるnote下書き貼り付け補助
