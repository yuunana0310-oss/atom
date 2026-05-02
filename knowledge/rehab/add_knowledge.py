"""
新しいナレッジファイルをRAGインデックスに追加するスクリプト
使い方:
    python add_knowledge.py                    # 差分インデックス（新規ファイルのみ追加）
    python add_knowledge.py --rebuild          # 全インデックス再構築
    python add_knowledge.py --search "股関節"  # 検索テスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from knowledge.rehab.rag_engine import RehabRAG


def main():
    args = sys.argv[1:]
    rag = RehabRAG()

    if '--rebuild' in args:
        print('インデックスを再構築します...')
        rag.index(force=True)
    elif '--search' in args:
        idx = args.index('--search')
        query = args[idx + 1] if idx + 1 < len(args) else '股関節'
        print(f'検索: {query}')
        results = rag.search(query, n_results=3)
        print(rag.format_context(results))
    else:
        print('差分インデックスを更新します（新規ファイルのみ）...')
        rag.index(force=False)
        print(f'現在のインデックス総数: {rag.collection.count()}件')


if __name__ == '__main__':
    main()
