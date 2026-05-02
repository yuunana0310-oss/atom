import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pro_rag_engine import ProRAG

class TextExtractionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_data = []
        self.skip_tags = {'script', 'style', 'header', 'footer', 'nav', 'noscript'}
        self.noise_keywords = {
            'テーマ別に探す', '報道・広報', '官公庁', '政策について', 
            '厚生労働省について', '統計情報', '申請・募集', 'サイトマップ',
            '文字サイズ', 'ホーム', '利用規約'
        }
        self.current_tag = []

    def handle_starttag(self, tag, attrs):
        self.current_tag.append(tag)

    def handle_endtag(self, tag):
        if self.current_tag:
            self.current_tag.pop()

    def handle_data(self, data):
        if not self.current_tag or self.current_tag[-1] not in self.skip_tags:
            t = data.strip()
            # ノイズキーワードを含む行や短すぎる行をスキップ
            if t and not any(k in t for k in self.noise_keywords) and len(t) > 5:
                self.text_data.append(t)

    def get_text(self):
        return '\n'.join([t for t in self.text_data if len(t) > 5])

def fetch_page_text(url):
    print(f"  [>>] 本文をスクレイピング中... : {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
        parser = TextExtractionParser()
        parser.feed(html)
        return parser.get_text()
    except Exception as e:
        print(f"  [ERROR] 本文取得に失敗: {e}")
        return "（本文の取得に失敗しました）"

# ========================================================
# [設定] 官公庁RSSソース（2026年最新版）
# ========================================================
LIST_OF_RSS = [
    {'name': '厚生労働省', 'tag': 'mhlw', 'url': 'https://www.mhlw.go.jp/stf/news.rdf'},
    {'name': 'e-Gov（パブコメ案件）', 'tag': 'egov', 'url': 'https://public-comment.e-gov.go.jp/rss/pcm_list.xml'},
    {'name': '内閣府', 'tag': 'nta', 'url': 'https://www.cao.go.jp/rss/index.xml'} # 国税庁の代わりに内閣府
]
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_rss(url):
    print(f"[INFO] ニュースを取得中: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        return ET.fromstring(xml_data)
    except Exception as e:
        print(f"[ERROR] 取得エラー: {e}")
        return None

def save_to_markdown(channel, agency_name, agency_tag):
    count = 0
    added_count = 0
    
    # 複数の名前空間に対応
    ns = {
        'rss': 'http://purl.org/rss/1.0/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'atom': 'http://www.w3.org/2005/Atom'
    }
    
    # 構造の自動判定
    items = []
    # 1. RDF 1.0
    items += channel.findall('.//rss:item', ns)
    # 2. RSS 2.0 (no namespace)
    if not items:
        items += channel.findall('.//item')
    # 3. Atom
    if not items:
        items += channel.findall('.//atom:entry', ns)

    for item in items:
        # title, link, description の抽出
        def get_val(tags, namespaces):
            for t in tags:
                elem = item.find(t, namespaces) if ':' in t else item.find(t)
                if elem is not None and elem.text:
                    return elem.text
            return None

        title = get_val(['rss:title', 'title', 'atom:title'], ns) or '無題'
        link = get_val(['rss:link', 'link', 'atom:link'], ns) or ''
        description = get_val(['rss:description', 'description', 'atom:summary'], ns) or '概要なし'
        pub_date = get_val(['dc:date', 'pubDate', 'atom:updated'], ns) or ''

        # アクセス負荷軽減
        time.sleep(2)
        body_text = fetch_page_text(link) if link else "（リンクなし）"
        
        description = description.replace('<', '&lt;').replace('>', '&gt;')
        
        file_id = "".join([c for c in title if c.isalnum() or c in ['_','-']])[:15]
        if not file_id:
            file_id = f"unknown_{count}"
            
        filename = f"news_industry_{file_id}.md"
        filepath = os.path.join(SAVE_DIR, filename)
        
        count += 1
        if os.path.exists(filepath):
            continue
            
        md_content = f"""---
title: {title}
source: {agency_name}
agency: {agency_tag}
url: {link}
date: {pub_date}
---

# {title}

**公式リンク:** [{link}]({link})
**公開日:** {pub_date}

## 概要
{description}

## ページ本文（スクレイピング結果）
{body_text[:3000]}
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        added_count += 1
        
        if count >= 5:
            break
            
    if added_count > 0:
        print(f"[SUCCESS] {added_count}件の最新ニュースを保存しました。")
    return added_count

if __name__ == "__main__":
    any_new = False
    for source in LIST_OF_RSS:
        print(f"\n--- {source['name']} の更新を確認 ---")
        root = fetch_rss(source['url'])
        if root is not None:
            saved = save_to_markdown(root, source['name'], source['tag'])
            if saved > 0:
                any_new = True
        time.sleep(2)

    if any_new:
        print("\n[INFO] RAG（知識ベース）を更新中...")
        try:
            rag = ProRAG()
            rag.index()
            print("[SUCCESS] 更新完了。")
        except Exception as e:
            print(f"[ERROR] RAG更新エラー: {e}")
    else:
        print("\n[INFO] 新着ニュースはありませんでした。")
