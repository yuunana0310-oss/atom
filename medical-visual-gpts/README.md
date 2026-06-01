# 医療ビジュアルGPTs完成パック 運用管理リポジトリ

ChatGPT用「医療ビジュアルGPTs完成パック」のInstructions、共通ナレッジ、作例、Threads投稿、note販売導線を管理するためのリポジトリです。

この管理環境は、最初はMarkdownとJSON Schemaを中心に運用し、必要に応じてGoogle Sheetsや簡単なWebアプリへ拡張できる形にしています。Canvaを主役にせず、ChatGPT/GPTs内で高品質な医療資料・SNS画像・患者説明資料・院内勉強会資料を作ることを前提にします。

## 管理対象

- 医療SNSサービス訴求ビジュアルGPT
- 患者説明・家族指導・自主トレ資料GPT
- 院内勉強会・医療者向け学習資料GPT
- 医療ビジュアル作例
- Threads投稿案と固定投稿・note導線
- GPT Instructionsの更新履歴
- 医療安全性、公開リスク、画像生成フローの共通ルール

## フォルダ構成

```text
medical-visual-gpts/
  README.md
  instructions/
    sns-medical-visual-gpt.md
    patient-family-exercise-gpt.md
    medical-seminar-gpt.md
  knowledge/
    design-principles.md
    safety-rules.md
    style-library.md
    generation-flow.md
    anatomy-accuracy-rules.md
  templates/
    threads-post-template.md
    note-sales-page-template.md
    carousel-structure-template.md
    a4-handout-template.md
    example-registration-template.md
    update-log-template.md
  examples/
    pressure-ulcer/
    heart-failure-rehab/
    fall-prevention/
    aspiration-prevention/
    frailty/
  database/
    examples.schema.json
    posts.schema.json
    gpt-versions.schema.json
    google-sheets-columns.md
  docs/
    web-app-expansion.md
```

## 運用方針

1. GPT本体に貼るInstructionsは `instructions/` に置く。
2. 3系統に共通する判断基準は `knowledge/` に分離する。
3. 作例を作ったら `examples/{theme}/example.md` に残す。
4. 投稿案は `templates/threads-post-template.md` を複製して使う。
5. note販売ページの改善案は `templates/note-sales-page-template.md` をベースにする。
6. GPTを更新したら `templates/update-log-template.md` に沿って変更履歴を残す。
7. Google Sheetsに移す場合は `database/google-sheets-columns.md` のCSVヘッダーを使う。

## 面倒を減らす登録コマンド

テンプレを開いてコピーする代わりに、PowerShellで質問に答えるだけでメモを作れます。

```powershell
.\medical-visual-gpts\tools\new-memo.cmd
```

作例メモを作る場合:

```powershell
.\medical-visual-gpts\tools\new-memo.cmd -Type example
```

Threads投稿メモを作る場合:

```powershell
.\medical-visual-gpts\tools\new-memo.cmd -Type post
```

Threads投稿メモではタイトル入力は不要です。投稿IDとファイル名は自動で作られます。

GPT更新メモを作る場合:

```powershell
.\medical-visual-gpts\tools\new-memo.cmd -Type update
```

作例メモは `examples/{テーマ}/`、投稿メモは `posts/`、更新メモは `update-logs/` に自動保存されます。

## 医療安全・公開リスクの基本方針

- 診断・治療の代替に見える表現は避ける。
- 「治る」「必ず改善」「安全保証」などの断定は使わない。
- 患者向け資料では「必要時は医療者に相談」「個別状況により異なる」を入れる。
- 子ども、患者、高齢者への指導表現はGPT公開時の警告リスクを意識する。
- 不安を煽る訴求より、理解・安心・相談につながる表現を優先する。

## 画像生成の基本フロー

画像生成はいきなり行わず、サイズ、枚数、用途、目的、ターゲット、媒体、入れたい要素、テイスト、情報量、主役を確認します。

カルーセルは1枚ずつ設計します。3枚依頼された場合、1枚の中に3枚分を詰め込まず、3枚それぞれを個別の成果物として扱います。

## Google Sheets運用

最初はMarkdownで管理し、投稿数や作例数が増えたらSheetsに転記します。主なシートは以下です。

- `examples`: 作例管理
- `threads_posts`: Threads投稿管理
- `gpt_versions`: GPT更新履歴

カラム定義は [database/google-sheets-columns.md](database/google-sheets-columns.md) を参照してください。

## 将来のWebアプリ化

Webアプリ化する場合も、最初はこのMarkdownとJSON Schemaをデータ設計の基準にします。詳細は [docs/web-app-expansion.md](docs/web-app-expansion.md) を参照してください。
