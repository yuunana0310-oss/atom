# 作例登録テンプレ

医療ビジュアル作例を1件ずつ登録するためのテンプレです。Markdownで記録し、必要に応じて `database/examples.schema.json` またはGoogle Sheetsへ転記します。

## 基本情報

| item | value |
|---|---|
| id | ex-YYYY-MM-001 |
| title |  |
| theme |  |
| category | 医療SNS用 / 院内勉強会用 / 患者説明用 / 家族指導用 / 自主トレ用 / 病態図解用 / 解剖図解用 / noteアイキャッチ用 |
| target_audience | 医療者 / 患者 / 家族 / 一般 / 管理職 |
| purpose |  |
| medium | Threads / Instagram / note / A4 / 院内資料 / LP / その他 |
| size |  |
| slide_count |  |
| style |  |
| main_visual |  |
| information_density | low / medium / high / very_high |
| gpt_used | sns-medical-visual / patient-family-exercise / medical-seminar |
| created_at |  |
| updated_at |  |

## 生成前の設計

- 主役:
- 読後に残したい理解:
- 入れる情報:
- 削る情報:
- 避けたい表現:
- 医療安全上の注意:
- 参考にしたナレッジ:

## 使用プロンプト

```text

```

## 出力画像

| item | value |
|---|---|
| output_image_url |  |
| local_path |  |
| thumbnail |  |
| final_used | true / false |

## 成功ポイント

- 

## 成功パターンとして再利用できること

| pattern | why_it_worked | reusable_instruction |
|---|---|---|
|  |  |  |

## 失敗ポイント

- 

## 画像生成時の失敗記録

| failure_type | detail | suspected_cause | correction_prompt | next_rule |
|---|---|---|---|---|
| 誤字 / 配置崩れ / 人体構造ミス / ラベルずれ / 情報不足 / ダサい / 1枚に詰め込み / フック弱い |  |  |  |  |

## 修正履歴

| version | date | change | reason | result |
|---|---|---|---|---|
| v1 |  | 初回生成 |  |  |

## 医療安全チェック

| check | ok | memo |
|---|---|---|
| 診断・治療の代替に見えない | [ ] |  |
| 治療効果を断定していない | [ ] |  |
| 安全保証に見えない | [ ] |  |
| 必要時の相談導線がある | [ ] |  |
| 患者・家族向けに不安を煽っていない | [ ] |  |
| 解剖・部位ラベルが大きく破綻していない | [ ] |  |
| 公開しても誤解されにくい | [ ] |  |

## Threads投稿との紐づけ

| item | value |
|---|---|
| threads_post_text |  |
| first_line_hook |  |
| posted_status | not_posted / draft / posted / reused |
| posted_url |  |
| result_memo |  |

## note導線の記録

| item | value |
|---|---|
| related_note |  |
| note_link |  |
| note_link_used | true / false |
| fixed_post誘導 |  |
| cta_type | fixed_post / note_soft / note_direct / none |
| sales_intent_level | low / medium / high |
| purchase_context | 通常 / 値上げ前 / 最終日 / 作例追加告知 |

## 次回改善

- 
