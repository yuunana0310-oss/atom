import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from ai_rag_engine import AITechRAG

# ZennのAIトピックのRSSフィード
RSS_URL = 'https://zenn.dev/topics/ai/feed'
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_rss():
    print(f"[INFO] RSSフィードを取得中: {RSS_URL}")
    req = urllib.request.Request(RSS_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        return ET.fromstring(xml_data)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None

def save_to_markdown(channel):
    count = 0
    added_count = 0
    
    # RSS 2.0のアイテムを取得
    for item in channel.findall('.//item'):
        title = item.find('title').text if item.find('title') is not None else '無題'
        link = item.find('link').text if item.find('link') is not None else ''
        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
        description = item.find('description').text if item.find('description') is not None else '概要なし'
        
        # HTMLタグなどが含まれている場合があるため簡易エスケープ
        description = description.replace('<', '&lt;').replace('>', '&gt;')
        
        # ファイル名をURLの末尾などで一意にする
        file_id = link.split('/')[-1] if link else f"unknown_{count}"
        filename = f"news_zenn_{file_id}.md"
        filepath = os.path.join(SAVE_DIR, filename)
        
        count += 1
        
        # 既に同じ記事が存在する場合はスキップ
        if os.path.exists(filepath):
            continue
            
        md_content = f"""---
title: {title}
source: Zenn (AIトピック)
url: {link}
date: {pub_date}
---

# {title}

**出典リンク:** [{link}]({link})
**公開日:** {pub_date}

## 概要
{description}
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        added_count += 1
        
        # 今回は最新の上位5件までに制限
        if count >= 5:
            break
            
    if added_count > 0:
        print(f"[SUCCESS] {added_count}件の新しいAIニュース記事をMarkdownとして保存しました。")
    return added_count

if __name__ == "__main__":
    root = fetch_rss()
    if root is not None:
        channel = root.find('channel')
        if channel is not None:
            saved = save_to_markdown(channel)
            if saved > 0:
                print("[INFO] RAGデータベース（AI脳）のインデックスを再構築・学習します...")
                try:
                    rag = AITechRAG()
                    rag.index()
                    print("[SUCCESS] 完了しました！エンジニアAI社員は最新の技術を学習しました。")
                except Exception as e:
                    print(f"インデックスの構築中にエラーが発生しました: {e}")
            else:
                print("新しい記事はありませんでした。（既にすべて学習済みです）")
