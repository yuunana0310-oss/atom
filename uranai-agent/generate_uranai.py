"""
霊視師 月詠 - 週間占い記事 自動生成エージェント
=====================================================
usage:
  python generate_uranai.py              # 全12星座を生成
  python generate_uranai.py --sign aries # 特定の星座だけ生成
  python generate_uranai.py --test       # おひつじ座だけテスト生成（確認用）
"""

import os
import sys
import io
import argparse

# Windowsのコンソールで日本語・絵文字を出力するためUTF-8に強制
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from datetime import datetime, timedelta
import anthropic
from dotenv import load_dotenv

# ============================================================
# 設定
# ============================================================

load_dotenv()

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
OUTPUT_DIR = BASE_DIR / "output"

# 12星座マスタ
ZODIAC_SIGNS = [
    {"en": "aries",       "jp": "おひつじ座", "num": "01"},
    {"en": "taurus",      "jp": "おうし座",   "num": "02"},
    {"en": "gemini",      "jp": "ふたご座",   "num": "03"},
    {"en": "cancer",      "jp": "かに座",     "num": "04"},
    {"en": "leo",         "jp": "しし座",     "num": "05"},
    {"en": "virgo",       "jp": "おとめ座",   "num": "06"},
    {"en": "libra",       "jp": "てんびん座", "num": "07"},
    {"en": "scorpio",     "jp": "さそり座",   "num": "08"},
    {"en": "sagittarius", "jp": "いて座",     "num": "09"},
    {"en": "capricorn",   "jp": "やぎ座",     "num": "10"},
    {"en": "aquarius",    "jp": "みずがめ座", "num": "11"},
    {"en": "pisces",      "jp": "うお座",     "num": "12"},
]

# ============================================================
# 日付ユーティリティ
# ============================================================

def get_week_info():
    """今週の月曜〜日曜の日付情報を返す"""
    today = datetime.now()
    # 月曜始まりに調整
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    
    # 週番号（年の第N週）
    week_num = today.isocalendar()[1]
    year = today.year
    
    return {
        "date_from": monday.strftime("%Y年%-m月%-d日") if sys.platform != "win32" else monday.strftime("%Y年%m月%d日").replace("年0", "年").replace("月0", "月"),
        "date_to": sunday.strftime("%Y年%-m月%-d日") if sys.platform != "win32" else sunday.strftime("%Y年%m月%d日").replace("年0", "年").replace("月0", "月"),
        "week_label": f"{year}年第{week_num}週",
        "folder_name": f"{year}-W{week_num:02d}",
    }

# ============================================================
# プロンプト構築
# ============================================================

def build_system_prompt():
    persona_path = PROMPTS_DIR / "persona.txt"
    return persona_path.read_text(encoding="utf-8")

def build_user_prompt(sign: dict, week_info: dict) -> str:
    template_path = PROMPTS_DIR / "weekly_fortune.txt"
    template = template_path.read_text(encoding="utf-8")
    
    return template.format(
        sign_jp=sign["jp"],
        sign_en=sign["en"],
        week_label=week_info["week_label"],
        date_from=week_info["date_from"],
        date_to=week_info["date_to"],
    )

# ============================================================
# API 呼び出し
# ============================================================

def generate_article(sign: dict, week_info: dict, client: anthropic.Anthropic) -> str:
    """Claude APIを呼び出して占い記事を生成する"""
    
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(sign, week_info)
    
    print(f"  [生成中] {sign['jp']} ...")
    
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    
    return message.content[0].text

# ============================================================
# ファイル保存
# ============================================================

def save_article(sign: dict, content: str, week_info: dict):
    """生成した記事をMarkdownファイルとして保存する"""
    
    week_dir = OUTPUT_DIR / week_info["folder_name"]
    week_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{sign['num']}_{sign['en']}.md"
    filepath = week_dir / filename
    
    # メタデータヘッダーを追加
    header = f"""---
生成日: {datetime.now().strftime('%Y-%m-%d %H:%M')}
星座: {sign['jp']}
週: {week_info['week_label']}
ペルソナ: 霊視師 月詠
---

"""
    filepath.write_text(header + content, encoding="utf-8")
    
    # 文字数カウント
    char_count = len(content)
    print(f"  [OK] 保存完了: {filepath.name} ({char_count:,}字)")
    return filepath

# ============================================================
# メイン処理
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="霊視師 月詠 - 週間占い記事生成エージェント")
    parser.add_argument("--sign", type=str, help="特定の星座のみ生成（英語名: aries, taurus, ...）")
    parser.add_argument("--test", action="store_true", help="おひつじ座のみテスト生成")
    args = parser.parse_args()
    
    # API クライアント初期化
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY が設定されていません")
        print("  .env ファイルを確認してください")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # 週情報取得
    week_info = get_week_info()
    
    print("=" * 60)
    print("[霊視師 月詠] 週間占い記事生成エージェント")
    print("=" * 60)
    print(f"[対象週] {week_info['week_label']} ({week_info['date_from']} ～ {week_info['date_to']})")
    print(f"[出力先] output/{week_info['folder_name']}/")
    print()
    
    # 生成対象の星座を決定
    if args.test:
        target_signs = [ZODIAC_SIGNS[0]]  # おひつじ座のみ
        print("[テストモード] おひつじ座のみ生成します")
    elif args.sign:
        target_signs = [s for s in ZODIAC_SIGNS if s["en"] == args.sign.lower()]
        if not target_signs:
            print(f"[ERROR] 星座名が見つかりません: {args.sign}")
            print(f"   有効な名前: {', '.join(s['en'] for s in ZODIAC_SIGNS)}")
            sys.exit(1)
    else:
        target_signs = ZODIAC_SIGNS
        print(f"[生成] 全 {len(ZODIAC_SIGNS)} 星座を生成します（約 {len(ZODIAC_SIGNS) * 2}～{len(ZODIAC_SIGNS) * 5} 分）")
    
    print()
    
    # 生成ループ
    generated_files = []
    errors = []
    
    for i, sign in enumerate(target_signs, 1):
        print(f"[{i}/{len(target_signs)}] {sign['jp']}")
        try:
            content = generate_article(sign, week_info, client)
            filepath = save_article(sign, content, week_info)
            generated_files.append(filepath)
        except Exception as e:
            print(f"  [ERROR] {e}")
            errors.append((sign["jp"], str(e)))
        print()
    
    # サマリー表示
    print("=" * 60)
    print(f"[完了] {len(generated_files)} 本の記事を生成しました")
    if errors:
        print(f"[警告] エラー {len(errors)} 件:")
        for sign_jp, err in errors:
            print(f"   - {sign_jp}: {err}")
    print()
    print(f"[ファイル] output\\{week_info['folder_name']}\\")
    print()
    print("[note投稿手順]")
    print("  1. output フォルダの .md ファイルを開く")
    print("  2. 内容をコピー")
    print("  3. note.com の記事作成画面に貼り付けて投稿！")
    print("=" * 60)

if __name__ == "__main__":
    main()
