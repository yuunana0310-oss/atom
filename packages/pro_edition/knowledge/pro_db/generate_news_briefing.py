import os
import json
import glob
import urllib.request
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # knowledge/pro_db
PRO_EDITION_DIR = os.path.dirname(os.path.dirname(BASE_DIR)) # packages/pro_edition
UI_DIR = os.path.join(PRO_EDITION_DIR, "ui")
NEWS_PATTERN = os.path.join(BASE_DIR, "news_industry_*.md")

def summarize_with_ai(api_key, text):
    """Gemini APIを使用してビジネス要約を生成する"""
    url = f"http://localhost:8000/api/chat" # 自作サーバー経由で叩く（APIキー等の隠蔽・一元化のため）
    # ただし今回はバッチ処理なので、直接Geminiを叩く
    gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
    prompt = f"""以下の行政ニュースの本文を読み、プロフェッショナルな視点で2〜3行のビジネス要約を作成してください。
指示：
- 「今回の要点」と「実務への影響」がわかるようにしてください。
- 挨拶や前置きは不要です。
- 要約のみを出力してください。

【本文内容】
{text[:3000]}
"""
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    
    try:
        req = urllib.request.Request(gemini_url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"  [WARNING] AI要約に失敗: {e}")
        return None

def generate(api_key=None):
    print("[INFO] インテリジェンス・ブリーフィング（AI要約検討版）を生成中...")
    news_files = glob.glob(NEWS_PATTERN)
    news_files.sort(key=os.path.getmtime, reverse=True)
    
    # カテゴリ別に集計
    briefing = {
        "all": [],
        "nta": [],
        "mhlw": [],
        "egov": []
    }
    
    # 各ソース上位5件程度を抽出
    source_counts = {"nta": 0, "mhlw": 0, "egov": 0}

    for path in news_files:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 簡易パース
        meta = {}
        for line in content.splitlines()[:10]:
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        
        agency = meta.get("agency", "egov")
        if source_counts.get(agency, 0) >= 5:
            continue

        title = meta.get("title", "無題")
        date = meta.get("date", "")
        
        print(f"  [+] 要約中: {title} ({agency})")
        
        # AI要約を試行
        ai_summary = None
        if api_key and "## ページ本文" in content:
            body_text = content.split("## ページ本文")[1].strip()
            ai_summary = summarize_with_ai(api_key, body_text)
        
        # フォールバック要約（従来のロジック）
        if not ai_summary:
            if "## 概要" in content:
                summary_part = content.split("## 概要")[1].split("##")[0].strip()
                if summary_part == "概要なし" and "## ページ本文" in content:
                    summary_part = content.split("## ページ本文")[1][:150].strip() + "..."
                ai_summary = summary_part.replace("\n", " ")[:150]
        
        item = {
            "title": title,
            "date": date,
            "summary": ai_summary if ai_summary else "詳細は本文を確認してください。",
            "url": meta.get("url", "#"),
            "agency": agency
        }
        
        briefing[agency].append(item)
        briefing["all"].append(item)
        source_counts[agency] = source_counts.get(agency, 0) + 1

    output_path = os.path.join(UI_DIR, "news_briefing.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)
    
    total = sum(len(v) for k, v in briefing.items() if k != "all")
    print(f"[SUCCESS] {total}件のニュースをカテゴリ別に整理して {output_path} に書き出しました。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", help="Gemini API Key for AI Summarization")
    args = parser.parse_args()
    generate(args.api_key)
