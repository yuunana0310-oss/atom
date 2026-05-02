"""
RAGエンジン - リハビリナレッジDB
medical部門（academic_researcher / medical_writer）が呼び出す

使い方:
    from knowledge.rehab.rag_engine import RehabRAG
    rag = RehabRAG()
    results = rag.search("股関節OAの運動療法", n_results=3)
    context = rag.format_context(results)
"""

import os
os.environ.pop("SSLKEYLOGFILE", None)  # NordLayer等のVPNドライバによるSSLエラー回避
import glob
import hashlib
import chromadb
from chromadb.utils import embedding_functions

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, '.chroma_db')
COLLECTION_NAME = 'rehab_knowledge'


def _get_embedding_fn():
    """埋め込みモデルの取得（sentence-transformers使用・無料・ローカル動作）"""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='paraphrase-multilingual-MiniLM-L12-v2'  # 日本語対応
    )


def _load_md_files() -> list[dict]:
    """knowledge/rehab/ 以下の全.mdファイルを読み込む（index.mdと_*.pyは除外）"""
    docs = []
    pattern = os.path.join(BASE_DIR, '**', '*.md')
    for path in glob.glob(pattern, recursive=True):
        filename = os.path.basename(path)
        if filename == 'index.md' or filename.startswith('_'):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # フロントマターからメタデータ抽出
        meta = {'source': os.path.relpath(path, BASE_DIR), 'filename': filename}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if ':' in line:
                        key, _, val = line.partition(':')
                        meta[key.strip()] = val.strip()
                content = parts[2].strip()
        # チャンク分割（見出し単位で分割、最大1000文字）
        chunks = _split_into_chunks(content, meta)
        docs.extend(chunks)
    return docs


def _split_into_chunks(text: str, meta: dict, max_chars: int = 800) -> list[dict]:
    """見出し単位でテキストを分割してチャンクを生成"""
    chunks = []
    current_heading = ''
    current_lines = []

    for line in text.splitlines():
        if line.startswith('#'):
            if current_lines:
                chunk_text = '\n'.join(current_lines).strip()
                if chunk_text:
                    chunks.append({
                        'text': chunk_text,
                        'heading': current_heading,
                        **meta
                    })
            current_heading = line.lstrip('#').strip()
            current_lines = [line]
        else:
            current_lines.append(line)
            # 最大文字数を超えたら強制分割
            if sum(len(l) for l in current_lines) > max_chars:
                chunk_text = '\n'.join(current_lines).strip()
                if chunk_text:
                    chunks.append({
                        'text': chunk_text,
                        'heading': current_heading,
                        **meta
                    })
                current_lines = []

    if current_lines:
        chunk_text = '\n'.join(current_lines).strip()
        if chunk_text:
            chunks.append({
                'text': chunk_text,
                'heading': current_heading,
                **meta
            })

    return chunks if chunks else [{'text': text[:max_chars], 'heading': '', **meta}]


class RehabRAG:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.embed_fn = _get_embedding_fn()
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={'description': 'リハビリ医療ナレッジDB'}
        )

    def index(self, force: bool = False):
        """ナレッジDBをインデックス化（force=Trueで強制再構築）"""
        if force:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embed_fn,
            )

        docs = _load_md_files()
        if not docs:
            print('インデックス対象のファイルが見つかりません')
            return

        ids, texts, metadatas = [], [], []
        for doc in docs:
            # IDはファイル名+チャンク内容のハッシュ
            doc_id = hashlib.md5(
                (doc['source'] + doc['text']).encode('utf-8')
            ).hexdigest()

            # 既存IDはスキップ（差分更新）
            if not force:
                existing = self.collection.get(ids=[doc_id])
                if existing['ids']:
                    continue

            text = doc.pop('text')
            ids.append(doc_id)
            texts.append(text)
            metadatas.append(doc)

        if ids:
            self.collection.add(ids=ids, documents=texts, metadatas=metadatas)
            print(f'{len(ids)}件のチャンクをインデックスに追加しました')
        else:
            print('新規追加なし（すべて既インデックス済み）')

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        """クエリに関連するチャンクを検索"""
        count = self.collection.count()
        if count == 0:
            print('インデックスが空です。先に rag_engine.py を実行してください')
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        output = []
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            output.append({
                'text': doc,
                'source': meta.get('source', ''),
                'title': meta.get('title', meta.get('heading', '')),
                'score': round(1 - distance, 3),  # 類似度（高いほど関連）
            })
        return output

    def format_context(self, results: list[dict]) -> str:
        """検索結果をプロンプト用のコンテキスト文字列に整形"""
        if not results:
            return ''
        lines = ['=== 参照ナレッジ（リハビリDB） ===']
        for i, r in enumerate(results, 1):
            lines.append(f'\n[{i}] {r["title"]} (出典: {r["source"]}, 類似度: {r["score"]})')
            lines.append(r['text'][:400])
            lines.append('...' if len(r['text']) > 400 else '')
        lines.append('=================================')
        return '\n'.join(lines)


if __name__ == '__main__':
    print('リハビリナレッジDBのインデックスを構築します...')
    rag = RehabRAG()
    rag.index()
    count = rag.collection.count()
    print(f'インデックス完了: {count}件のチャンクが登録されました')
    print()

    # 動作確認
    test_queries = [
        '股関節OAの運動療法エビデンス',
        '嚥下障害の理学療法アプローチ',
        '画像所見と臨床症状の解離',
    ]
    for q in test_queries:
        print(f'テストクエリ: {q}')
        results = rag.search(q, n_results=2)
        for r in results:
            print(f'  → [{r["score"]}] {r["title"]} ({r["source"]})')
        print()
