# RAS（Research Automation System）システム概要
> Claude Code への引き継ぎ・説明用ドキュメント  
> 作成日: 2026-04-12

---

## 🏗️ RASとは何か

RAS（Research Automation System）は、GeminiやNotebookLMで生成した研究サマリーを  
**ローカルのObsidian互換Vault（Markdown）+ ChromaDB（ベクトルDB）**に自動的に取り込み、  
各AIエージェントが自然言語で検索・参照できるようにするための**ナレッジ管理パイプライン**です。

### 目的
- Gemini / NotebookLM の出力（研究サマリー・文献まとめ）を永続化する
- 各エージェントが「最新の医療・リハビリ知識」をRAG経由で参照できるようにする
- ユーザーの手間を最小限に抑えた「one-click」知識蓄積を実現する

---

## 📁 ディレクトリ構造

```
C:\Users\yuuna\agens\
│
├── RAS_IMPORT_BOX\              ← ★投入口（ここにMD/TXTを入れる）
│   └── （処理後は自動削除される）
│
├── RASサマリー投入用.md          ← サマリーをペーストして「インポートして」と伝える用
├── paste_to_ras.ps1             ← クリップボード→RASへワンクリック投入スクリプト
│
└── knowledge\
    ├── import_research.py       ← ★メインのインポートスクリプト
    └── research_synthesis\
        ├── synthesis_rag_engine.py  ← ★RAGエンジン本体
        ├── vault\               ← ★処理済みMDファイルの保存先（Obsidian Vault）
        │   ├── 2026-04-12_股関節リハビリテーション：深層統合レポート.md
        │   ├── 2026-04-12_膝関節：最新エビデンス論文リスト.md
        │   └── ...（日付_タイトル.md 形式）
        └── .chroma_db\          ← ベクトルDB（ChromaDB永続化）
```

---

## ⚙️ データフロー（全体像）

```
[ユーザー]
    │
    ├─① クリップボードにサマリーをコピー
    │       ↓
    │   paste_to_ras.ps1 を実行（ダブルクリック）
    │       ↓
    │   RAS_IMPORT_BOX\clipboard_import.md に保存
    │
    ├─② または RASサマリー投入用.md に貼り付けて
    │       「インポートして」とAntigravityに伝える
    │
    └─③ または RAS_IMPORT_BOX に直接MDファイルをコピー

         ↓↓↓ ここからは自動処理 ↓↓↓

[import_research.py]
    │
    ├─ RAS_IMPORT_BOX の .md / .txt を読み込む
    ├─ 「# 大見出し」単位で自動分割
    ├─ 日付+タイトルでファイル名生成（例: 2026-04-12_股関節OA.md）
    ├─ フロントマター（title / date / source / type）を自動付与
    ├─ knowledge/research_synthesis/vault/ に保存
    ├─ 処理済み元ファイルを削除
    └─ SynthesisRAG.index() を呼び出してベクトルDBを更新

[SynthesisRAG（synthesis_rag_engine.py）]
    │
    ├─ vault/ 以下の全MDファイルを読み込む
    ├─ 見出し単位でチャンク分割（最大1500文字/チャンク）
    ├─ paraphrase-multilingual-MiniLM-L12-v2 でエンベディング生成
    └─ ChromaDB（.chroma_db/）に永続保存（差分のみ追加）
```

---

## 🔍 RAG検索の使い方（各エージェントが呼び出す方法）

```python
from knowledge.research_synthesis.synthesis_rag_engine import SynthesisRAG

rag = SynthesisRAG()

# 検索（デフォルト2件）
results = rag.search("股関節OAの運動療法エビデンス", n_results=3)

# プロンプトに挿入できる形式に整形
context = rag.format_context(results)
print(context)
```

### 出力例
```
=== 統合サマリー（NotebookLM/Gemini由来） ===

[1] Hall論文：股関節OA詳細技術ノート (出典: vault/2026-04-12_..., 精度: 0.842)
（本文テキスト）

[2] 股関節リハビリテーション：深層統合レポート (出典: ..., 精度: 0.791)
（本文テキスト）

=========================================
```

---

## 📝 インポート時のファイル仕様

### 入力ファイル（RAS_IMPORT_BOX に入れるもの）
- 拡張子: `.md` または `.txt`
- 文字コード: UTF-8 推奨
- 複数テーマを一括投入する場合は **`# タイトル`（H1見出し）** で区切る

```markdown
# 股関節OAの最新エビデンス
（ここにサマリー本文）

# 膝関節リハビリの系統的レビュー
（ここにサマリー本文）
```
→ 上記は **2つの別ファイルとして** vault に保存される

### 出力ファイル（vault に生成されるもの）
```markdown
---
title: 股関節OAの最新エビデンス
date: 2026-04-12 15:30:00
source: NotebookLM/Gemini
type: synthesis
---

# 股関節OAの最新エビデンス
（本文）
```

---

## 🚦 現在の制限事項・未実装部分

| 項目 | 状況 |
|------|------|
| カテゴリ自動仕分け | ❌ 未実装。vault/ 直下に全ファイルが平置きされる |
| 重複検知 | ✅ MD5ハッシュで差分のみ追加（同一内容は二重登録しない） |
| 自動実行（ファイル監視） | ❌ 未実装。手動でスクリプト実行が必要 |
| インボックスの別パス | `inbox/` フォルダも存在するが現在は未使用 |
| Obsidian連携 | `.obsidian/` は存在するが自動同期は未設定 |

---

## 🛠️ エンベディングモデル情報

| 項目 | 値 |
|------|-----|
| モデル名 | `paraphrase-multilingual-MiniLM-L12-v2` |
| ライブラリ | `sentence-transformers` |
| 対応言語 | 多言語（日本語対応） |
| チャンクサイズ | 最大1500文字（統合サマリー向けに通常より大きめ） |
| DBエンジン | ChromaDB（永続化モード） |

---

## 📌 Claude Code が作業する際の注意点

1. **RAGの参照タイミング**: 医療・リハビリ・研究に関するユーザー指示を受けた場合、 `SynthesisRAG.search()` で知識を引いてからプロンプトを構築すること
2. **インポートの実行**: `import_research.py` は `knowledge/` ディレクトリをカレントにして実行する必要はなく、どこからでも `python c:\Users\yuuna\agens\knowledge\import_research.py` で動く
3. **vault の直接編集**: vault 内のMDファイルを直接編集した場合、`rag.index(force=True)` でインデックスを再構築すること
4. **ChromaDB の場所**: `.chroma_db/` は `knowledge/research_synthesis/` 直下にある（隠しフォルダ）
