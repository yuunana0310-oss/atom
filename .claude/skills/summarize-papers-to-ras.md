# PT向け論文サマリー自動生成スキル

**スキル名**: `summarize-papers-to-ras`

医学論文をPT（理学療法士）向けの実践的なMarkdownサマリーに変換し、研究自動化システム(RAS)のインポートボックスに自動配置します。

## 概要

このスキルは以下の処理を実行します：

1. **標準入力から複数論文を受け取る** （区切り文字: `---`）
2. **Claude APIで各論文をサマリー化** （モデル: `claude-opus-4-6`）
3. **PT向けMarkdown形式で整形** （背景・対象・方法・結果・結論・臨床応用）
4. **RAS_IMPORT_BOXに自動保存** （タイムスタンプ付きファイル）
5. **SynthesisRAGで自動インデックス化** （RAG検索対応）

## 使用方法

### スキル実行

```
/summarize-papers-to-ras
```

または直接スクリプト実行：
```bash
python C:\Users\yuuna\agens\knowledge\papers_to_vault.py
```

### 入力形式

標準入力から論文テキストを以下の形式で入力：

```
[論文1のテキスト（タイトル、背景、方法、結果など）]
---
[論文2のテキスト]
---
[論文3のテキスト]
```

**入力終了方法:**
- Linux/Mac: `Ctrl+D`
- Windows (PowerShell): `Ctrl+Z` → `Enter`

### 出力形式

**保存先:** `C:\Users\yuuna\agens\RAS_IMPORT_BOX\papers_summary_YYYYMMDD_HHMMSS.md`

**ファイル構成:** H1見出し (`# `) で区切られたMarkdown

## PT向けサマリー構成

### 背景
- **記載内容:** この研究が必要だった理由、臨床的背景
- **文字数:** 2-3文

### 対象
- **記載内容:** 対象患者の特性、サンプルサイズ、選定基準
- **形式:** 箇条書き

### 方法
- **記載内容:** 介入内容、実施期間、測定項目
- **形式:** 箇条書き

### 結果
- **記載内容:** 主要な成果と数値、効果サイズ
- **形式:** 簡潔な段落 + 数値データ

### 結論
- **記載内容:** エビデンスレベル、信頼性、制限事項

### 臨床応用（最重要）
- **推奨患者:** 対象患者群の具体例（PT が判断しやすいもの）
- **実装方法:** 具体的なプログラム内容・実施頻度・期間
- **注意点:** 禁忌・安全性・モニタリング項目

## 依存環境

### 必須パッケージ

```bash
pip install anthropic
```

### 環境変数

**ANTHROPIC_API_KEY**
- 必須: Yes
- 説明: Claude API認証キー
- 設定: `.claude/settings.local.json` で管理
  ```json
  {
    "env": {
      "ANTHROPIC_API_KEY": "sk-ant-xxxxxxxx"
    }
  }
  ```

## エラーハンドリング

### API キーが見つからない

**エラー:**
```
Error: ANTHROPIC_API_KEY が設定されていません
```

**対応:**
1. `.claude/settings.local.json` で環境変数を設定
2. Claude Code を再起動

### anthropic ライブラリが未インストール

**対応:**
```bash
pip install anthropic
```

### 入力テキストが空

**エラー:**
```
エラー: テキストが入力されていません
```

**対応:** 論文テキストを入力してから `Ctrl+D` / `Ctrl+Z+Enter` を実行

### API レート制限（429エラー）

**対応:**
1. 処理を一時停止
2. 30秒以上待機
3. 再度実行

## 次のステップ

### 1. サマリー生成後

スキル実行 または：
```bash
python C:\Users\yuuna\agens\knowledge\papers_to_vault.py
```

### 2. RAS_IMPORT_BOX から Vault への移行

```bash
python C:\Users\yuuna\agens\knowledge\import_research.py
```

これにより：
- ファイルが `research_synthesis/vault/` に移動
- フロントマター（メタデータ）が付与
- SynthesisRAG インデックスが自動更新

### 3. コンテンツ作成時の RAG 活用

```python
from research_synthesis.synthesis_rag_engine import SynthesisRAG

rag = SynthesisRAG()
results = rag.search("膝OAの運動療法", n_results=3)
context = rag.format_context(results)
```

## トラブルシューティング

| 症状 | 原因 | 対応 |
|---|---|---|
| スクリプトが開始されない | PythonやAPIキーの環境変数未設定 | `settings.local.json` で設定 |
| 論文サマリーが生成されない | API キーが無効 | キーを再確認 |
| RAS_IMPORT_BOX にファイルが保存されない | パスが存在しない | ディレクトリを手動作成 |

## 関連リソース

- **詳細なワークフロー**: `.claude/rules/papers-research-workflow.md`
- **スクリプトドキュメント**: `.claude/scripts/papers_to_vault.md`
- **医療コンテンツ作成ガイド**: `CLAUDE.md` の「医療・リハビリ」セクション
