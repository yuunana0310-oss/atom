# リハビリナレッジDB インデックス

RAGシステム用ナレッジベース。academic_researcher / medical_writer が自動参照する。

## 更新履歴
| 日付 | 内容 |
|------|------|
| 2026-04-06 | 初版作成・ディレクトリ構築 |
| 2026-04-06 | 既存資産（股関節OA×2件、嚥下PT×1件）をmd変換・格納 |

---

## ディレクトリ構成

```
knowledge/rehab/
├── papers/         医療論文・ガイドラインの要約
├── reports/        過去の調査レポート（md変換済み）
├── conditions/     疾患別まとめ
└── index.md        ← このファイル
```

---

## ナレッジ一覧

### reports/（調査レポート）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| hip_oa_imaging_clinical_dissociation.md | 股関節OA：画像所見と臨床症状の解離 | 2026-04-06 |
| hip_oa_pt_treatment_approach.md | 股関節OA：理学療法士の治療アプローチ | 2026-04-06 |
| swallowing_pt_evidence_report.md | 嚥下障害：PT向けエビデンスレポート | 2026-04-06 |

### conditions/（疾患別まとめ）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| hip_oa.md | 変形性股関節症 総合まとめ | 2026-04-06 |
| hip_oa_resistance_training.md | 股関節OA向けレジスタンストレーニング エビデンスまとめ | 2026-04-07 |

### papers/（論文・ガイドライン）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| prohip_trial_nejm_2024.md | PROHIP試験：THA vs レジスタンストレーニング（NEJM 2024） | 2026-04-07 |

---

## 追加ルール

1. **形式**: 必ずMarkdown（.md）で保存
2. **ファイル名**: 英語スネークケース（例: `knee_oa_exercise.md`）
3. **ヘッダー必須**: 各ファイル冒頭に以下を記載

```markdown
---
title: （日本語タイトル）
category: papers | reports | conditions
tags: [タグ1, タグ2]
source: （出典URL or 元ファイル名）
added: YYYY-MM-DD
---
```

4. **index.mdを必ず更新**: ファイル追加時にこのファイルの一覧に追記する
