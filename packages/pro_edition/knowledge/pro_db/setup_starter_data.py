"""
スターターデータ一括収集スクリプト
====================================
このスクリプトを一度実行するだけで、士業専用AIデータベースの
「初期知識（スターターデータ）」を自動で収集します。

収集先（すべて国が公式に公開しているデータ）:
  1. 国税庁 タックスアンサー（税務Q&A）
  2. 厚生労働省 労働基準法に関するQ&A
  3. 厚生労働省 報道発表（最新ニュース）

実行方法: python setup_starter_data.py
所要時間: 約5〜10分（サーバーへの負荷軽減のため3秒ずつ休止）
"""

import os
os.environ.pop("SSLKEYLOGFILE", None)
import sys
import ssl
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

# SSL証明書の検証をスキップ（企業ネットワーク環境での動作保証のため）
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR   = os.path.join(BASE_DIR, "..", "pro_db")
os.makedirs(SAVE_DIR, exist_ok=True)

# ============================================================
# 収集先の設定（URLとカテゴリ名のリスト）
# ============================================================
# プロ版向けに件数を増やし、より実用的なデータセットにします
STARTER_SOURCES = [
    {
        "name": "国税庁タックスアンサー_所得税",
        "type": "scrape_links",
        "url":  "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/shotoku.htm",
        "category": "tax",
        "max_pages": 100, # 大幅増強
    },
    {
        "name": "厚労省_最新ニュース（報道発表）",
        "type": "rss",
        "url":  "https://www.mhlw.go.jp/stf/news.rdf",
        "category": "labor_news",
        "max_pages": 30,
    },
    {
        "name": "厚労省_労働基準法Q&A",
        "type": "scrape_links",
        "url":  "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/faq/index.html",
        "category": "labor_faq",
        "max_pages": 50,
    },
]

# ============================================================
# ユーティリティ
# ============================================================
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self.skip  = {"script","style","header","footer","nav","noscript","aside"}
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)

    def handle_endtag(self, tag):
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self._tag_stack and self._tag_stack[-1] in self.skip:
            return
        t = data.strip()
        if len(t) > 8:
            self.texts.append(t)

    def get_text(self):
        return "\n".join(self.texts)


def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            encoding = r.headers.get_content_charset("utf-8")
            return r.read().decode(encoding, errors="ignore")
    except Exception as e:
        print(f"    [ERROR] 取得失敗: {e}")
        return ""


def html_to_text(html: str) -> str:
    p = TextExtractor()
    p.feed(html)
    return p.get_text()


def save_md(filename: str, title: str, url: str, body: str, category: str):
    filepath = os.path.join(SAVE_DIR, filename)
    if os.path.exists(filepath):
        return False
    content = f"""---
title: {title}
source: スターターデータ（{category}）
url: {url}
---

# {title}

**出典:** [{url}]({url})

## 本文
{body[:3000]}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def sanitize(name: str) -> str:
    import re
    name = re.sub(r'[\\/:*?"<>|\s]', "_", name)
    return name[:40]


# ============================================================
# 収集ロジック
# ============================================================
def collect_rss(source: dict) -> int:
    print(f"  [RSS] {source['name']} を取得中...")
    html = fetch_html(source["url"])
    if not html:
        return 0
    try:
        root = ET.fromstring(html.encode("utf-8"))
    except Exception:
        return 0

    ns    = {"rss": "http://purl.org/rss/1.0/"}
    items = root.findall(".//rss:item", ns) or root.findall(".//item")
    count = 0
    for item in items[:source["max_pages"]]:
        title_el = item.find("rss:title", ns) or item.find("title")
        link_el  = item.find("rss:link",  ns) or item.find("link")
        title = (title_el.text or "無題").strip() if title_el is not None else "無題"
        link  = (link_el.text  or "").strip()  if link_el  is not None else ""
        if not link:
            continue
        time.sleep(3)
        print(f"    → スクレイピング: {title[:30]}...")
        body = html_to_text(fetch_html(link))
        fname = f"starter_{source['category']}_{sanitize(title)}.md"
        if save_md(fname, title, link, body, source["category"]):
            count += 1
    return count


def collect_scrape_single(source: dict) -> int:
    print(f"  [SCRAPE] {source['name']} を取得中...")
    time.sleep(3)
    html = fetch_html(source["url"])
    if not html:
        return 0
    body = html_to_text(html)
    fname = f"starter_{source['category']}_{sanitize(source['name'])}.md"
    if save_md(fname, source["name"], source["url"], body, source["category"]):
        print(f"    → 保存完了: {fname}")
        return 1
    print(f"    → 既存ファイル（スキップ）")
    return 0


def collect_scrape_links(source: dict) -> int:
    """ページ内のリンクを探して個別ページを収集する"""
    print(f"  [LINKS] {source['name']} のリンクを収集中...")
    html = fetch_html(source["url"])
    if not html:
        return 0

    parsed_url = urllib.parse.urlparse(source["url"])
    base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    links = []

    class LinkParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                href = dict(attrs).get("href", "")
                if not href or "#" in href or "javascript" in href: return
                
                # NTA or MHLW 用のフィルタ（簡易版）
                if "taxanswer" in href or "/stf/seisakunitsuite/bunya/" in href:
                    full = urllib.parse.urljoin(source["url"], href)
                    if full not in links and full.startswith(base_origin):
                        links.append(full)
    
    lp = LinkParser()
    lp.feed(html)

    count = 0
    print(f"    → {len(links)}個のリンクを特定。最大{source['max_pages']}件を収集します。")
    for lnk in links[:source["max_pages"]]:
        time.sleep(3)
        page_html = fetch_html(lnk)
        if not page_html:
            continue
        body = html_to_text(page_html)
        title_part = lnk.split("/")[-1].replace(".htm","").replace(".html","")
        fname = f"starter_{source['category']}_{sanitize(title_part)}.md"
        if save_md(fname, f"{source['category']}_{title_part}", lnk, body, source["category"]):
            print(f"    → 保存: {fname}")
            count += 1
    return count


# ============================================================
# メイン
# ============================================================
if __name__ == "__main__":
    print("=" * 58)
    print("  スターターデータ一括収集スクリプト")
    print("  ※ サーバー負荷軽減のため各ページ間に3秒の休止を入れています")
    print("=" * 58)

    total = 0
    for source in STARTER_SOURCES:
        print(f"\n【{source['name']}】")
        stype = source.get("type", "rss")
        if stype == "rss":
            n = collect_rss(source)
        elif stype == "scrape_single":
            n = collect_scrape_single(source)
        elif stype == "scrape_links":
            n = collect_scrape_links(source)
        else:
            n = 0
        print(f"  → {n}件 取得・保存完了")
        total += n

    print(f"\n{'='*58}")
    print(f"  合計 {total}件のスターターデータを収集しました！")
    print(f"  保存先: {SAVE_DIR}")
    print(f"{'='*58}")

    if total > 0:
        print("\nAIデータベース（RAG）に学習させます...")
        try:
            sys.path.insert(0, SAVE_DIR)
            from pro_rag_engine import ProRAG
            rag = ProRAG()
            rag.index()
            print("学習完了！AI社員が即戦力になりました。")
        except Exception as e:
            print(f"[WARN] 手動で pro_rag_engine.py を実行してください: {e}")

    print("\n完了！")
