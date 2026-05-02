"""
統合リサーチDB - RAGエンジン
Gemini / NotebookLM から取得した統合サマリーを専門に扱う。
各エージェント（Lead Engineer, Academic Researcher等）が呼び出す。

使い方:
    from knowledge.research_synthesis.synthesis_rag_engine import SynthesisRAG
    rag = SynthesisRAG()
    results = rag.search("最新のリハビリテーションAI動向", n_results=3)
    context = rag.format_context(results)
"""

import os
os.environ.pop("SSLKEYLOGFILE", None)
import glob
import hashlib
import chromadb
from chromadb.utils import embedding_functions

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, 'vault')
CHROMA_DIR = os.path.join(BASE_DIR, '.chroma_db')
COLLECTION_NAME = 'research_synthesis'


def _get_embedding_fn():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='paraphrase-multilingual-MiniLM-L12-v2'
    )


def _load_md_files() -> list[dict]:
    docs = []
    # vaultディレクトリ以下のファイルを対象にする
    pattern = os.path.join(VAULT_DIR, '**', '*.md')
    for path in glob.glob(pattern, recursive=True):
        filename = os.path.basename(path)
        if filename.startswith('_'):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        meta = {'source': os.path.relpath(path, BASE_DIR), 'filename': filename}
        
        # フロントマター処理
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if ':' in line:
                        key, _, val = line.partition(':')
                        meta[key.strip()] = val.strip()
                content = parts[2].strip()
        
        chunks = _split_into_chunks(content, meta)
        docs.extend(chunks)
    return docs


def _split_into_chunks(text: str, meta: dict, max_chars: int = 1500) -> list[dict]:
    """
    統合サマリーは大局的な情報が多いため、通常のナレッジ（800文字）より
    少し大きめのチャンク（1500文字）で分割し、文脈を維持しやすくする。
    """
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


class SynthesisRAG:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.embed_fn = _get_embedding_fn()
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={'description': '統合リサーチ・サマリーDB'}
        )

    def index(self, force: bool = False):
        if force:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embed_fn,
            )

        docs = _load_md_files()
        if not docs:
            print('インデックス対象のファイルが vault に見つかりません')
            return

        ids, texts, metadatas = [], [], []
        for doc in docs:
            doc_id = hashlib.md5(
                (doc['source'] + doc['text']).encode('utf-8')
            ).hexdigest()

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
            print(f'{len(ids)}件のチャンクを統合インデックスに追加しました')
        else:
            print('新規サマリーなし（学習済み）')

    def search(self, query: str, n_results: int = 2) -> list[dict]:
        """
        検索。サマリーは要点そのものなので、少なめ（標準2件）の
        検索結果でも十分な情報が得られる。
        """
        count = self.collection.count()
        if count == 0:
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
                'score': round(1 - distance, 3),
            })
        return output

    def format_context(self, results: list[dict]) -> str:
        if not results:
            return ""
        lines = ['=== 統合サマリー（NotebookLM/Gemini由来） ===']
        for i, r in enumerate(results, 1):
            lines.append(f'\n[{i}] {r["title"]} (出典: {r["source"]}, 精度: {r["score"]})')
            lines.append(r['text'])
        lines.append('=========================================')
        return '\n'.join(lines)


if __name__ == '__main__':
    rag = SynthesisRAG()
    rag.index()
