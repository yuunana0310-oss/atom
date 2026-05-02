# papers_to_vault.py ドキュメント

**所在:** `C:\Users\yuuna\agens\knowledge\papers_to_vault.py`

**役割:** 医学論文のテキストをPT向けMarkdownサマリーに変換し、RAS_IMPORT_BOXに自動保存。

## 実行方法

```bash
python C:\Users\yuuna\agens\knowledge\papers_to_vault.py
```

または Claude Code スキル経由：
```
/summarize-papers-to-ras
```

---

## 入出力仕様

### 入力

**形式:** 標準入力（stdin）

**構成:** 複数の論文テキストを `---` で区切り

```
[論文1テキスト]
---
[論文2テキスト]
---
[論文3テキスト]
```

**入力終了:**
- Linux/Mac: `Ctrl+D`
- Windows (PowerShell): `Ctrl+Z` → `Enter`

### 出力

**保存先:** `C:\Users\yuuna\agens\RAS_IMPORT_BOX\papers_summary_YYYYMMDD_HHMMSS.md`

**形式:** Markdown（H1見出しで区切られた複数論文）

```markdown
# [論文1タイトル]

## 背景
...

## 対象
...

## 方法
...

## 結果
...

## 結論
...

## 臨床応用
...

# [論文2タイトル]
...
```

---

## 依存パッケージ

```
anthropic>=0.7.0
```

インストール：
```bash
pip install anthropic
```

---

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API 認証キー |

設定例（settings.local.json）:
```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-xxxxxxxx"
  }
}
```

---

## エラーハンドリング

### E1: ImportError (anthropic ライブラリなし)

**症状:**
```
Error: anthropic ライブラリがインストールされていません
pip install anthropic を実行してください
```

**対応:**
```bash
pip install anthropic
```

### E2: ANTHROPIC_API_KEY が設定されていない

**症状:**
```
Error: ANTHROPIC_API_KEY が設定されていません
```

**対応:** `.claude/settings.local.json` で設定してから再起動

### E3: 入力テキストが空

**症状:**
```
エラー: テキストが入力されていません
```

**対応:** 論文テキストを入力してから入力終了コマンドを実行

### E4: API エラー

| エラー | 原因 | 対応 |
|---|---|---|
| `RateLimitError` | API レート制限 | 30秒以上待機して再実行 |
| `AuthenticationError` | API キーが無効 | キーを再確認 |
| `APIConnectionError` | ネットワーク障害 | インターネット接続確認 |

---

## 実行例

### 例1: 単一論文

```bash
$ python papers_to_vault.py
1件の論文が検出されました。処理を開始します...

[1/1] 論文を処理中... ✓

============================================================
✓ サマリー生成完了
  保存先: C:\Users\yuuna\agens\RAS_IMPORT_BOX\papers_summary_20260412_143022.md

次のステップ:
  python C:\Users\yuuna\agens\knowledge\import_research.py
============================================================
```

### 例2: 複数論文

```bash
3件の論文が検出されました。処理を開始します...

[1/3] 論文を処理中... ✓
[2/3] 論文を処理中... ✓
[3/3] 論文を処理中... ✓
```

---

## コード構成

### 主要関数

#### `get_api_key()`
環境変数から Claude API キーを取得

#### `generate_pt_summary(client, paper_text)`
Claude API を呼び出してPT向けサマリーを生成

- **モデル:** `claude-opus-4-6`
- **最大トークン:** 2,000

#### `main()`
メイン処理（入力読込 → API呼出 → ファイル保存）

---

## トラブルシューティング

### Q: スクリプトが起動しない

**A:** Python と anthropic がインストールされているか確認

```bash
python --version
pip show anthropic
```

### Q: API キーエラーが出る

**A:** キー形式を確認（`sk-ant-` で始まること）、settings.local.json で設定推奨

### Q: 論文テキストの入力方法

**A:** PubMed / Google Scholar からテキストをコピー&ペースト。区切りは `---` （ハイフン3つ）

### Q: RAS_IMPORT_BOX にファイルが保存されない

**A:** ディレクトリのパーミッション確認、または手動作成

```bash
mkdir -p "C:\Users\yuuna\agens\RAS_IMPORT_BOX"
```

---

## 次のステップ

生成後は import_research.py を実行：

```bash
python C:\Users\yuuna\agens\knowledge\import_research.py
```

詳細は `.claude/rules/papers-research-workflow.md` を参照。
