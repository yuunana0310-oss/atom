# 📱 Threads運用部 コマンドルーター (/threads)

## 概要
Threadsに特化した完全自律型SNS運用部門です。
ネタ収集 → 分析 → 執筆 → 投稿 → 計測 → 監視 のサイクルをClaudeが直接担います。

## 所属エージェントと担当領域

| エージェント | ファイル | 担当 |
|---|---|---|
| Researcher | `agents/threads_researcher.md` | ネタ・トレンド収集、投稿候補リスト生成 |
| Analyst | `agents/threads_analyst.md` | 過去データ分析、Writerへの指示書作成 |
| Writer | `agents/threads_writer.md` | 投稿文生成（採点7.0未満は再生成） |
| Poster | `agents/threads_poster.md` | スケジュール管理・投稿実行 |
| Fetcher | `agents/threads_fetcher.md` | 24h後メトリクス収集・履歴記録 |
| Supervisor | `agents/threads_supervisor.md` | 異常監視・KILL_SWITCH管理・週次レポート |

## 標準フロー（週次サイクル）

```
Researcher → Analyst → Writer → Poster
                                   ↓（24時間後）
Supervisor ← Fetcher ←←←←←←←←←←←
```

1. **Researcher**: 週5〜10件のネタを `data/research_queue.json` に書き出し
2. **Analyst**: 過去データを分析し `data/analyst_brief.json` に指示書を作成
3. **Writer**: 指示書＋ネタを元に投稿文を生成、`data/drafts.json` に書き出し
4. **Poster**: スケジュールに従い投稿実行、`data/queue.json` を更新
5. **Fetcher**: 24時間後にメトリクス取得、`data/post_history.json` に追記
6. **Supervisor**: 全プロセスを監視、異常時はKILL_SWITCHを発動

## 起動ルール（司令塔向け）

- **「Threadsの投稿を作って」**: Researcher → Analyst → Writer の順で動かし、`drafts.json` を確認させてからPosterへ渡す
- **「今週の成果を教えて」**: Supervisor に `post_history.json` を元に週次レポートを作成させる
- **「投稿が伸びていない」**: Analyst に直近データの分析と改善指示書の更新を依頼
- **「止めて」**: Supervisor に KILL_SWITCH の生成を指示

## データファイル一覧

| ファイル | 役割 |
|---|---|
| `data/research_queue.json` | Researcherのネタリスト |
| `data/analyst_brief.json` | Analystの指示書 |
| `data/drafts.json` | Writerの生成投稿（下書き） |
| `data/queue.json` | 投稿キュー・実行記録 |
| `data/post_history.json` | メトリクス込みの投稿履歴 |
| `data/weekly_report.json` | Supervisorの週次レポート |
| `data/KILL_SWITCH` | 存在すれば全停止 |

## 参照すべきナレッジファイル（atom）

| ファイル | 参照するエージェント | 内容 |
|---|---|---|
| `knowledge/atom/01_profile.md` | Writer | 発信者の人物像・bio・アフィリンク |
| `knowledge/atom/02_target.md` | Researcher, Writer | ターゲット・ペイン・ゲイン |
| `knowledge/atom/03_genre.md` | Researcher, Analyst | テーマカテゴリ・優先順位 |
| `knowledge/atom/04_expertise.md` | Writer | 専門知識・独自体験・使えるフレーズ |
| `knowledge/atom/05_writing_rules.md` | Writer | トーン・フォーマット・CTA |
| `knowledge/atom/06_reference_posts.md` | Writer, Analyst | 参考投稿パターン＋atom応用例 |
| `knowledge/atom/07_prohibitions.md` | Researcher, Writer | NGワード・やってはいけないこと |
| `knowledge/atom/08_strategy.md` | Analyst, Supervisor | 運用モード・KPI・ロードマップ |
