# -*- coding: utf-8 -*-
"""
note.com 投稿スクリプト
使い方:
  python post_to_note.py <記事.md> [オプション]

オプション:
  --price 300          販売価格（0=無料）
  --tags AI Claude     ハッシュタグ（スペース区切り）
  --publish            下書きではなく即時公開する（省略時は下書き保存）
  --eyecatch image.png アイキャッチ画像

例:
  python post_to_note.py AI/claude_code_article.md --price 300 --tags AI ClaudeCode
  python post_to_note.py AI/claude_code_article.md --price 300 --publish
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# .env 読み込み
load_dotenv(Path(__file__).parent / ".env")

EMAIL    = os.getenv("NOTE_EMAIL")
PASSWORD = os.getenv("NOTE_PASSWORD")
USERNAME = os.getenv("NOTE_USERNAME")

def main():
    parser = argparse.ArgumentParser(description="note.com に記事を投稿する")
    parser.add_argument("article", help="Markdownファイルのパス（このスクリプトからの相対パス）")
    parser.add_argument("--price", type=int, default=0, help="販売価格（デフォルト: 0=無料）")
    parser.add_argument("--tags", nargs="*", default=[], help="ハッシュタグ（# なしで指定）")
    parser.add_argument("--publish", action="store_true", help="即時公開（省略時は下書き保存）")
    parser.add_argument("--eyecatch", default=None, help="アイキャッチ画像パス")
    args = parser.parse_args()

    # 認証情報チェック
    if not EMAIL or not PASSWORD or not USERNAME:
        print("❌ .env ファイルに NOTE_EMAIL / NOTE_PASSWORD / NOTE_USERNAME を設定してください")
        print("   .env.example を参考に .env を作成してください")
        sys.exit(1)

    # 記事ファイルチェック
    article_path = Path(__file__).parent / args.article
    if not article_path.exists():
        print(f"❌ 記事ファイルが見つかりません: {article_path}")
        sys.exit(1)

    mode = "publish" if args.publish else "draft"
    price_str = f"{args.price} yen" if args.price > 0 else "free"
    print(f"\n[Post Settings]")
    print(f"   File : {article_path.name}")
    print(f"   Price: {price_str}")
    print(f"   Tags : {args.tags or 'none'}")
    print(f"   Mode : {mode}")
    print()

    if args.publish:
        confirm = input("⚠️  即時公開します。よろしいですか？ (y/N): ").strip().lower()
        if confirm != "y":
            print("キャンセルしました")
            sys.exit(0)

    # NoteClient2 で投稿
    try:
        from NoteClient2 import NoteClient2
    except ImportError:
        print("❌ NoteClient2 がインストールされていません")
        print("   pip install NoteClient2 && playwright install chromium")
        sys.exit(1)

    session_file = str(Path(__file__).parent / ".note_session.json")

    print("🔐 ログイン中...")
    client = NoteClient2(
        email=EMAIL,
        password=PASSWORD,
        user_urlname=USERNAME,
        session_file=session_file,
    )

    print(f"📤 {mode}中...")
    result = client.publish(
        title=_extract_title(article_path),
        md_file_path=str(article_path),
        hashtags=args.tags,
        price=args.price,
        eyecatch_path=args.eyecatch,
        is_publish=args.publish,
    )

    if result.get("ok"):
        data = result["data"]
        print(f"\n✅ {mode}完了！")
        if data.get("edit_url"):
            print(f"   編集URL  : {data['edit_url']}")
        if data.get("public_url"):
            print(f"   公開URL  : {data['public_url']}")
        if not args.publish:
            print("\n   👆 編集URLを開いて内容を確認後、手動で公開してください")
    else:
        err = result.get("error", {})
        print(f"\n❌ 投稿失敗: {err.get('type', 'Unknown')}")
        print(f"   詳細: {err.get('detail', err)}")
        sys.exit(1)


def _extract_title(md_path: Path) -> str:
    """Markdownの1行目 `# タイトル` からタイトルを抽出する"""
    with open(md_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    # タイトルが見つからない場合はファイル名
    return md_path.stem


if __name__ == "__main__":
    main()
