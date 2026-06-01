# GPT Instructions 更新履歴テンプレ

GPT Instructions、ナレッジ、テンプレートを変更したときに使う更新履歴テンプレです。軽量運用ではこのMarkdownを複製して使い、件数が増えたら `database/gpt-versions.schema.json` またはGoogle Sheetsへ転記します。

## 基本情報

| item | value |
|---|---|
| version | v0.1.0 |
| previous_version |  |
| date |  |
| target_gpt | sns-medical-visual / patient-family-exercise / medical-seminar / common |
| updated_file |  |
| updated_section |  |
| update_type | minor / major / safety / design / flow / sales |
| status | draft / reviewed / published / reverted |
| public_safe | true / false / review_needed |
| reviewer |  |

## 変更理由

- 

## 変更内容サマリー

- 追加したこと:
- 削除したこと:
- 強めたルール:
- 弱めたルール:
- 今回あえて触らないこと:

## 変更前

```text

```

## 変更後

```text

```

## 期待する効果

- 

## 出力テスト

| test_theme | expected_output | result | memo |
|---|---|---|---|
| 褥瘡資料 |  | pass / fail / review |  |
| 患者説明資料 |  | pass / fail / review |  |
| Threads作例投稿 |  | pass / fail / review |  |
| カルーセル複数枚 |  | pass / fail / review |  |

## リスク確認

| check | result | memo |
|---|---|---|
| 医療安全性 | ok / review_needed / ng |  |
| 公開リスク | ok / review_needed / ng |  |
| 誇大表現リスク | ok / review_needed / ng |  |
| 子ども・患者・高齢者への表現 | ok / review_needed / ng |  |
| 診断・治療代替に見える表現 | ok / review_needed / ng |  |
| 画像生成フローの逸脱 | ok / review_needed / ng |  |
| note販売導線が強すぎない | ok / review_needed / ng |  |
| Canva依存が強くなっていない | ok / review_needed / ng |  |

## 公開前チェックリスト

| check | ok | memo |
|---|---|---|
| GPTに貼る本文の文字数を確認した | [ ] |  |
| 公開用と自分用の指示が混ざっていない | [ ] |  |
| 医療安全ルールが残っている | [ ] |  |
| 対話してから生成する流れが残っている | [ ] |  |
| カルーセルを1枚にまとめない指示が残っている | [ ] |  |
| 誇大な販売表現が入っていない | [ ] |  |
| GPT公開警告が出そうな表現を確認した | [ ] |  |
| 旧版へ戻す判断基準を書いた | [ ] |  |

## ロールバック条件

- 

## notes

- 
