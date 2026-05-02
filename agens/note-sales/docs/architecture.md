# note-sales アーキテクチャ

## システム概要

Threads→note の半自動販売システム。
Threads運用部（既存システム）とは「読み取り・受け渡し」のみで連携する。

## 状態遷移

```
pain_collected
  → candidate_generated   (researcher)
  → human_approved        (selector: 人間が必ず承認)
  → draft_created         (note_writer)
  → editor_review         (editor)
  → publish_ready         (editor)
  → published             (note_publisher: manual前提)
  → promo_brief_ready     (promo_brief_generator)
  → analyzed              (note_analyzer)
  → pattern_updated       (knowledge_base)
```

## モジュール責務

| モジュール | 責務 | Threads連携 |
|---|---|---|
| pain_intake | 読者の悩みを収集・登録 | Threadsコメントを読むだけ |
| researcher | Claude APIで候補テーマ生成 | なし |
| selector | 人間承認フロー（自動承認なし） | なし |
| note_writer | Claude APIで下書き生成 | なし |
| editor | 品質スコアリング・フィードバック | なし |
| note_publisher | note.com公開（manual前提） | なし |
| promo_brief_generator | Threads運用部への素材生成のみ | JSONファイルを出力するだけ |
| performance_importer | 成績JSONを読むだけ | JSONファイルを読むだけ |
| note_analyzer | パフォーマンス分析 | なし |
| knowledge_base | パターン更新 | なし |

## ディレクトリ構成

```
note-sales/
├── src/
│   ├── cli.py              # Typer CLIエントリポイント
│   ├── core/
│   │   ├── models.py       # Pydanticモデル・状態定義
│   │   ├── settings.py     # 設定読み込み
│   │   └── logger.py       # ロガー設定
│   ├── agents/             # 各モジュールのエージェント（Task 2〜）
│   ├── services/
│   │   └── orchestrator.py # run-daily / run-weekly の制御
│   ├── adapters/
│   │   ├── storage_sqlite.py  # SQLite CRUD
│   │   └── storage_json.py    # JSON読み書き・エクスポート
│   ├── prompts/            # Claude APIプロンプト（Task 2〜）
│   └── utils/
│       └── dry_run.py      # dry-runガード
├── tests/
├── config/
│   ├── settings.yaml
│   └── .env.example
└── data/
    ├── raw/performance/    # ← Threads運用部からの成績JSONを置く場所
    ├── processed/promo_briefs/ # → Threads運用部へのブリーフ出力先
    └── db/
```

## Threads運用部との連携インターフェース

### → Threads運用部への出力
- `data/processed/promo_briefs/promo_brief_*.json`
- 投稿本文ではなく、投稿の方向性（ブリーフ）のみを渡す

### ← Threads運用部からの入力
- `data/raw/performance/` 以下のJSONファイル
- フォーマットは `PerformanceRecord` モデルを参照

## 品質ゲート

- 最低スコア: 7.0（`config/settings.yaml` の `quality.min_score`）
- スコア未満の場合、次工程に進めない
- 人間承認なしで `human_approved` 状態にはできない
- `publish_mode=manual` のため、自動公開は行わない
