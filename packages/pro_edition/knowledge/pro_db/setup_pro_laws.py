import os
os.environ["SSLKEYLOGFILE"] = "" # WindowsでのPermissionError回避策（物理ファイルへの書き込みを無効化）
if "SSLKEYLOGFILE" in os.environ: os.environ.pop("SSLKEYLOGFILE") 
import sys
import ssl
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# SSL設定を即座に作成（エラーチェック）
try:
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
except Exception as e:
    # 最終手段：環境変数がどうしてもエラーになる場合
    _SSL_CTX = ssl._create_unverified_context()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR  = os.path.join(BASE_DIR, "laws")
os.makedirs(SAVE_DIR, exist_ok=True)

# ------------------------------------------------------------
# ターゲット法令セット（士業別の主要法令）
# ------------------------------------------------------------
# 検索に失敗した場合のバックアップID（主要なもの）
BACKUP_LAW_IDS = {
    "労働基準法": "322AC0000000049",
    "所得税法": "340AC0000000033",
    "法人税法": "340AC0000000034",
    "消費税法": "363AC0000000108",
    "会社法": "417AC0000000086",
    "民法": "129AC0000000089"
}

LAW_PACKS = {
    "labor": ["労働基準法", "労働契約法", "労働安全衛生法", "最低賃金法"],
    "tax": ["所得税法", "法人税法", "消費税法", "相続税法"]
}

def fetch_api(endpoint: str, params: dict = None) -> dict:
    url = f"https://laws.e-gov.go.jp/api/2/{endpoint}"
    if params:
        # 手動でクエリ文字列を作成（日本語対応のため）
        parts = []
        for k, v in params.items():
            parts.append(f"{k}={urllib.parse.quote(str(v))}")
        url += "?" + "&".join(parts)
    
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=20) as r:
            content = r.read().decode("utf-8")
            return json.loads(content)
    except Exception as e:
        print(f"  [ERROR] API取得失敗: {e} (URL: {url})")
        return {}

def convert_to_markdown(law_data: dict) -> str:
    """e-Gov API V2の再帰的なJSON構造 (tag/children) をMarkdownに変換する"""
    full_text = law_data.get("law_full_text", {})
    if not full_text:
        return f"解析エラー: law_full_textが見つかりません = {json.dumps(law_data)[:200]}"
        
    info = law_data.get("law_info", {})
    title = law_data.get("revision_info", {}).get("law_title", "無題")
    num   = info.get("law_num", "")
    
    md = [
        "---",
        f"title: {title}",
        f"law_num: {num}",
        f"source: e-Gov API V2",
        "---",
        "",
        f"# {title}",
        f"（法令番号: {num}）",
        "",
    ]
    
    def walk_tree(node, depth=2):
        if isinstance(node, str):
            return node + "\n"
        
        if not isinstance(node, dict):
            return ""
            
        res = ""
        tag = node.get("tag", "")
        children = node.get("children", [])
        
        # 見出しタグの処理
        if tag in ["ChapterTitle", "SectionTitle", "ArticleTitle"]:
            prefix = "#" * min(depth, 6)
            text = "".join([c if isinstance(c, str) else "" for c in children])
            res += f"\n{prefix} {text}\n\n"
            return res # 見出しはここで完結

        # 本文タグの処理
        if tag in ["Sentence", "ParagraphSentence", "ItemSentence"]:
            text = ""
            for msg in children:
                if isinstance(msg, str): text += msg
                elif isinstance(msg, dict):
                    #  ruby要素などは中身だけ抽出
                    text += "".join([c if isinstance(c, str) else "" for c in msg.get("children", [])])
            res += f"{text}\n"

        # 子供を再帰的に探索
        # ただし、目次(TOC)はスキップして本文(MainProvision)を優先する
        if tag == "TOC":
            return ""

        for child in children:
            if isinstance(child, dict):
                # 階層が深まるタグ
                new_depth = depth + 1 if tag in ["Chapter", "Section", "Article"] else depth
                res += walk_tree(child, new_depth)
            elif isinstance(child, str) and tag not in ["Sentence", "ParagraphSentence", "ItemSentence"]:
                # 直書きのテキスト（稀なケース）
                res += child + "\n"
                
        return res

    md.append(walk_tree(full_text))
    return "\n".join(md)

def setup():
    print("=" * 60)
    print("  士業専用法令データ構築ツール (Pro Edition)")
    print("  ※ 関連する施行令・施行規則も自動収集します")
    print("=" * 60)

    for pack_name, law_list in LAW_PACKS.items():
        print(f"\n【{pack_name.upper()}パック】を開始...")
        for base_name in law_list:
            print(f"\n--- {base_name} 関連を検索中 ---")
            
            # バックアップIDがあれば優先使用
            backup_id = BACKUP_LAW_IDS.get(base_name)
            
            # 「法」「施行令」「施行規則」をセットで取得
            search_queries = [base_name, f"{base_name}施行令", f"{base_name}施行規則"]
            
            for query in search_queries:
                law_id = None
                law_title = query
                
                # 最初だけバックアップID（完全一致時）
                if query == base_name and backup_id:
                    law_id = backup_id
                else:
                    res = fetch_api("laws", {"law_name": query})
                    laws = res.get("law_list", [])
                    if laws:
                        target = next((l for l in laws if l.get("law_title") == query), laws[0])
                        law_id = target.get("law_id")
                        law_title = target.get("law_title")

                if not law_id:
                    print(f"  [SKIP] {query} は見つかりませんでした。")
                    continue
                
                filename = f"law_{law_id}.md"
                filepath = os.path.join(SAVE_DIR, filename)
                if os.path.exists(filepath):
                    print(f"  [EXIST] {law_title} は取得済みです。")
                    continue
                
                print(f"  → 取得中: {law_title} (ID: {law_id})...")
                data_res = fetch_api(f"law_data/{law_id}")
                if not data_res: continue
                
                md = convert_to_markdown(data_res)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md)
                print(f"  [OK] 保存完了: {filename}")
                time.sleep(2) # 紳士的ディレイ

if __name__ == "__main__":
    setup()
    print("\n[FINISH] 法令セットの構築が完了しました。")
