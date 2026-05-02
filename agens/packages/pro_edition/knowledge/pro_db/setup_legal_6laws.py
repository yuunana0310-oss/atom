import os
import sys
import ssl
import json
import time
import urllib.request
import urllib.parse

# SSL設定: WindowsでのPermissionError回避
os.environ.pop("SSLKEYLOGFILE", None)
_SSL_CTX = ssl._create_unverified_context()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
# 弁護士パック専用のディレクトリ
SAVE_DIR  = os.path.join(BASE_DIR, "legal_pack")
os.makedirs(SAVE_DIR, exist_ok=True)

# ------------------------------------------------------------
# ターゲット法令：基本六法 + 会社法
# ------------------------------------------------------------
LEGAL_6_LAWS = [
    "日本国憲法", "民法", "商法", "会社法", 
    "民事訴訟法", "刑法", "刑事訴訟法"
]

def fetch_api(endpoint: str, params: dict = None) -> dict:
    url = f"https://laws.e-gov.go.jp/api/2/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
            content = r.read().decode("utf-8")
            return json.loads(content)
    except Exception as e:
        print(f"  [ERROR] API取得失敗: {e} (URL: {url})")
        return {}

def convert_to_markdown(law_data: dict) -> str:
    full_text = law_data.get("law_full_text", {})
    info = law_data.get("law_info", {})
    title = law_data.get("revision_info", {}).get("law_title", "無題")
    num   = info.get("law_num", "")
    
    md = ["---", f"title: {title}", f"law_num: {num}", "source: e-Gov API V2", "---", "", f"# {title}\n"]
    
    def walk_tree(node, depth=2):
        if isinstance(node, str): return node + "\n"
        if not isinstance(node, dict): return ""
        res = ""
        tag = node.get("tag", "")
        children = node.get("children", [])
        if tag in ["ChapterTitle", "SectionTitle", "ArticleTitle"]:
            text = "".join([c if isinstance(c, str) else "" for c in children])
            res += f"\n{'#' * min(depth, 6)} {text}\n\n"
            return res
        if tag in ["Sentence", "ParagraphSentence", "ItemSentence"]:
            text = ""
            for msg in children:
                if isinstance(msg, str): text += msg
                elif isinstance(msg, dict):
                    text += "".join([c if isinstance(c, str) else "" for c in msg.get("children", [])])
            res += f"{text}\n"
        if tag == "TOC": return ""
        for child in children:
            if isinstance(child, dict):
                res += walk_tree(child, depth + 1 if tag in ["Chapter", "Section", "Article"] else depth)
        return res

    md.append(walk_tree(full_text))
    return "\n".join(md)

def setup():
    print("=" * 60)
    print("  【Ultimate Edition】基本六法・リーガルパック構築")
    print("=" * 60)

    for title in LEGAL_6_LAWS:
        law_id = None
        
        # まず名称でIDを検索
        print(f"\n--- {title} を検索中 ---")
        res = fetch_api("laws", {"law_name": title})
        law_list = res.get("law_list", [])
        if law_list:
            # 完全一致を優先
            target = next((l for l in law_list if l.get("law_title") == title), law_list[0])
            law_id = target.get("law_id")
            actual_title = target.get("law_title")
        
        if not law_id:
            print(f"  [SKIP] {title} のIDが見つかりませんでした")
            continue

        filename = f"law_{law_id}.md"
        filepath = os.path.join(SAVE_DIR, filename)
        
        if os.path.exists(filepath):
            print(f"  [EXIST] {actual_title} は取得済みです")
            continue
            
        print(f"  → 取得中: {actual_title} (ID: {law_id})...")
        data = fetch_api(f"law_data/{law_id}")
        if not data: continue
        
        md = convert_to_markdown(data)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"  [OK] 保存完了: {filename}")
        time.sleep(3) # 紳士的ディレイ

if __name__ == "__main__":
    setup()
    print("\n[FINISH] リーガルパックの構築が完了しました。")
