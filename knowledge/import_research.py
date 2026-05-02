"""
リサーチ・サマリー・インポーター
inbox 内のファイルを読み込み、自動分割・メタデータ付与を行って vault へ移動する。
その後、SynthesisRAGを呼び出してインデックスを更新する。
"""

import os
import re
import datetime
import shutil
from research_synthesis.synthesis_rag_engine import SynthesisRAG

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INBOX_DIR = os.path.join(os.path.dirname(BASE_DIR), 'RAS_IMPORT_BOX')
VAULT_DIR = os.path.join(BASE_DIR, 'research_synthesis', 'vault')



def process_inbox():
    if not os.path.exists(INBOX_DIR):
        print(f"Error: {INBOX_DIR} が存在しません")
        return

    files = [f for f in os.listdir(INBOX_DIR) if f.endswith('.md') or f.endswith('.txt')]
    if not files:
        print("Inboxは空です。ファイルを配置してください。")
        return

    for filename in files:
        inpath = os.path.join(INBOX_DIR, filename)
        print(f"処理中: {filename}...")
        
        with open(inpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 大見出し (# ) で分割を試みる（一括コピペ対応）
        sections = re.split(r'\n(?=# )', '\n' + content)
        sections = [s.strip() for s in sections if s.strip()]

        for i, section in enumerate(sections):
            # タイトルの抽出（1行目の見出しから）
            title_match = re.match(r'^#\s*(.*)', section)
            title = title_match.group(1).strip() if title_match else f"synthesis_{datetime.date.today()}_{i}"
            
            # ファイル名の生成（記号を除去）
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
            out_filename = f"{datetime.date.today()}_{safe_title}.md"
            out_path = os.path.join(VAULT_DIR, out_filename)

            # フロントマターの準備
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            frontmatter = f"---\ntitle: {title}\ndate: {now}\nsource: NotebookLM/Gemini\ntype: synthesis\n---\n\n"
            
            # 見出しが欠落している場合（フロントマターにはあるが本文にはない場合）の補完
            output_content = frontmatter + (section if section.startswith('#') else f"# {title}\n\n{section}")

            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"  -> 保存完了: {out_filename}")

        # 処理が終わったファイルを削除（ご要望通り）
        os.remove(inpath)
        print(f"  -> インポート完了: {filename} を削除しました")


    # インデックス更新
    print("\nインデックスを更新中...")
    rag = SynthesisRAG()
    rag.index()


if __name__ == '__main__':
    process_inbox()
