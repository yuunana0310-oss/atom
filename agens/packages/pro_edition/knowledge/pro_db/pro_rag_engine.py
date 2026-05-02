"""
士業・専門家向けナレッジDB - RAGエンジン
agents/expert_assistant.md が呼び出して使用します。

使用例:
    from pro_rag_engine import ProRAG
    rag = ProRAG()
    results = rag.search("最新の労働基準法改正", n_results=3)
"""

import os
os.environ.pop("SSLKEYLOGFILE", None)
import glob
import hashlib
import chromadb
from chromadb.utils import embedding_functions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, '.chroma_db')
COLLECTION_NAME = 'pro_industry_knowledge'

def _get_embedding_fn():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='paraphrase-multilingual-MiniLM-L12-v2'
    )

def _load_md_files() -> list[dict]:
    docs = []
    # 複数のサブディレクトリ（パック）を想定
    pattern = os.path.join(BASE_DIR, '**', '*.md')
    for path in glob.glob(pattern, recursive=True):
        filename = os.path.basename(path)
        if filename == 'index.md' or filename.startswith('_'):
            continue
        
        # フォルダ構造からメタデータを推測
        rel_path = os.path.relpath(path, BASE_DIR)
        dir_name = os.path.dirname(rel_path)
        
        # ソース種別の判定ロジック
        source_type = 'general'
        if 'law' in dir_name or filename.startswith('law_'): source_type = 'law'
        elif 'precedent' in dir_name: source_type = 'precedent'
        elif 'qa' in dir_name: source_type = 'qa'
        elif 'news' in dir_name: source_type = 'news'
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        meta = {
            'source': rel_path, 
            'filename': filename,
            'source_type': source_type,
            'tier': 'pro' if 'legal' in dir_name or 'precedent' in dir_name else 'basic'
        }
        
        # フロントマターの解析
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

def _split_into_chunks(text: str, meta: dict, max_chars: int = 800) -> list[dict]:
    chunks = []
    current_heading = ''
    current_lines = []
    
    for line in text.splitlines():
        if line.startswith('#'):
            # 本文（見出しではない行）が含まれているか確認
            has_body = any(not l.startswith('#') and l.strip() for l in current_lines)
            if has_body:
                chunk_text = '\n'.join(current_lines).strip()
                chunks.append({'text': chunk_text, 'heading': current_heading, **meta.copy()})
                current_lines = [] # 本文を格納したので空にする
                
            current_heading = line.lstrip('#').strip()
            current_lines.append(line)
        else:
            current_lines.append(line)
            
        # サイズ上限を超えたら分割
        if sum(len(l) for l in current_lines) > max_chars:
            chunk_text = '\n'.join(current_lines).strip()
            if chunk_text:
                chunks.append({'text': chunk_text, 'heading': current_heading, **meta.copy()})
            current_lines = []

    if current_lines:
        chunk_text = '\n'.join(current_lines).strip()
        chunks.append({'text': chunk_text, 'heading': current_heading, **meta.copy()})
        
    # ゴミデータの最終フィルタリング（短すぎる、または見出ししか無いチャンクを弾く）
    valid_chunks = []
    for c in chunks:
        non_headers = [l for l in c['text'].splitlines() if not l.startswith('#') and l.strip()]
        if len(c['text']) > 40 and non_headers:
            valid_chunks.append(c)

    return valid_chunks if valid_chunks else [{'text': text[:max_chars], 'heading': '', **meta.copy()}]

class ProRAG:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.embed_fn = _get_embedding_fn()
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={'description': '士業・専門家向け多層型ナレッジDB'}
        )

    def index(self, force: bool = False):
        if force:
            try:
                self.client.delete_collection(COLLECTION_NAME)
            except:
                pass
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embed_fn,
            )
        
        docs = _load_md_files()
        if not docs:
            print('[WARN] インデックス対象のファイルが見つかりません')
            return
        
        print(f'[RAG] 全{len(docs)}個のチャンクを分析中...')
        
        existing_ids = set()
        if not force:
            count = self.collection.count()
            if count > 0:
                existing_data = self.collection.get(include=[])
                existing_ids = set(existing_data['ids'])

        new_ids, new_texts, new_metadatas = [], [], []
        for i, doc in enumerate(docs):
            # 元データを破壊しないよう、text以外をメタデータに
            text_to_index = doc.pop('text')
            
            # ソース名とテキストからユニークID生成
            unique_key = f"{doc['source']}_{i}_{text_to_index}"
            doc_id = hashlib.md5(unique_key.encode('utf-8')).hexdigest()
            
            if doc_id not in existing_ids:
                new_ids.append(doc_id)
                new_texts.append(text_to_index)
                new_metadatas.append(doc)

        if new_ids:
            batch_size = 100
            for i in range(0, len(new_ids), batch_size):
                end = min(i + batch_size, len(new_ids))
                self.collection.add(
                    ids=new_ids[i:end],
                    documents=new_texts[i:end],
                    metadatas=new_metadatas[i:end]
                )
                print(f'[RAG] 登録進捗: {end}/{len(new_ids)}')
            print(f'[SUCCESS] {len(new_ids)}件の新規ナレッジを追加しました')
        else:
            print('[INFO] データベースは最新です')

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        count = self.collection.count()
        if count == 0: return []
        
        results = self.collection.query(query_texts=[query], n_results=min(n_results, count))
        output = []
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            dist = results['distances'][0][i]
            output.append({
                'text': doc,
                'source': meta.get('source', ''),
                'title': meta.get('title', meta.get('heading', '解説')),
                'source_type': meta.get('source_type', 'general'),
                'tier': meta.get('tier', 'basic'),
                'score': round(1 - dist, 3),
            })
        return output

    def format_context(self, results: list[dict]) -> str:
        if not results:
            return ''
        lines = ['=== 参照ナレッジ（事務所専用DB） ===']
        for i, r in enumerate(results, 1):
            lines.append(f'\n[{i}] {r["title"]} (出典: {r["source"]}, 類似度: {r["score"]})')
            lines.append(r['text'][:400])
            lines.append('...' if len(r['text']) > 400 else '')
        lines.append('=================================')
        return '\n'.join(lines)

if __name__ == '__main__':
    print('事務所専用データベースの構築を開始します...')
    rag = ProRAG()
    rag.index()
    print(f'完了: 現在のDB登録件数は {rag.collection.count()} 件です。')
