# リハビリナレッジDB インデックス

RAGシステム用ナレッジベース。academic_researcher / medical_writer が自動参照する。

← [[index.md|マスターハブへ戻る]] / 関連: [[MOC_リサーチVault]]

## 更新履歴
| 日付 | 内容 |
|------|------|
| 2026-04-06 | 初版作成・ディレクトリ構築 |
| 2026-04-06 | 既存資産（股関節OA×2件、嚥下PT×1件）をmd変換・格納 |
| 2026-05-10 | Obsidian wikilink化 |

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
| [[hip_oa_imaging_clinical_dissociation]] | 股関節OA：画像所見と臨床症状の解離 | 2026-04-06 |
| [[hip_oa_pt_treatment_approach]] | 股関節OA：理学療法士の治療アプローチ | 2026-04-06 |
| [[swallowing_pt_evidence_report]] | 嚥下障害：PT向けエビデンスレポート | 2026-04-06 |

### conditions/（疾患別まとめ）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| [[hip_oa]] | 変形性股関節症 総合まとめ | 2026-04-06 |
| [[hip_oa_resistance_training]] | 股関節OA向けレジスタンストレーニング エビデンスまとめ | 2026-04-07 |

### papers/（論文・ガイドライン）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| [[prohip_trial_nejm_2024]] | PROHIP試験：THA vs レジスタンストレーニング（NEJM 2024） | 2026-04-07 |

### 制度・報酬（運用・現場対応）
| ファイル | 内容 | 追加日 |
|----------|------|--------|
| [[当院向け 2026年度リハ診療報酬改定 役割別対策]] | 2026年度改定：一般病床36床・療養病床60床 役割別対策 | 2026-05-21 |

---

## 関連リサーチ（research_synthesis/vault/）

股関節OA関連の深層レポート・論文サマリーは [[MOC_股関節OA研究]] にまとめている。

- [[2026-04-12_股関節OA：Hall論文詳細技術ノート]]
- [[2026-04-12_股関節リハビリテーション：深層統合レポート]]
- [[2026-04-12_synthesis_2026-04-12_0]]（Hip Muscle Strengthening systematic review）

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
