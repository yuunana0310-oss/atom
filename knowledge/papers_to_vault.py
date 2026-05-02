#!/usr/bin/env python3
"""
PT向け論文サマリー生成 → RAS_IMPORT_BOX へ自動投入スクリプト

使い方:
  python papers_to_vault.py

入力: 標準入力から複数の論文テキストを受け取る（区切りは「---」）
出力: C:\Users\yuuna\agens\RAS_IMPORT_BOX\papers_summary_{timestamp}.md に保存
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Claude API関連
try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic ライブラリがインストールされていません")
    print("pip install anthropic を実行してください")
    sys.exit(1)


def get_api_key():
    """APIキーを環境変数から取得"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)
    return api_key


def generate_pt_summary(client, paper_text):
    """
    Claude APIを使用してPT向けサマリーを生成

    Args:
        client: Anthropic クライアント
        paper_text: 論文のテキスト

    Returns:
        PT向けサマリー（Markdown形式）
    """

    system_prompt = """あなたは理学療法士向けの医学論文サマリーエキスパートです。

以下の構成でサマリーを作成してください：

# [論文タイトル]

## 背景
なぜこの研究が必要だったのか、臨床的背景を2-3文で説明。

## 対象
対象患者の特性、サンプルサイズ、選定基準を簡潔に記載。

## 方法
介入内容、実施期間、測定項目を箇条書きで記載。

## 結果
主要な成果と数値、効果サイズを簡潔に記載。

## 結論
この研究のエビデンスレベル、信頼性、制限事項を記載。

## 臨床応用
**推奨患者**: （対象患者群の具体例）
**実装方法**: （具体的なプログラム内容・実施頻度・期間）
**注意点**: （禁忌・安全性上の注意・モニタリング項目）

---

重要な注意：
- 簡潔で実践的に。冗長な説明は避ける。
- 数値や具体的な結果を記載する。
- 臨床応用では、PTがすぐに実装できる具体的な内容を心がける。
- 信頼できる情報のみを記載し、推測は「推測される」と明記する。
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"以下の論文をPT向けサマリーにまとめてください：\n\n{paper_text}"
            }
        ]
    )

    return message.content[0].text


def main():
    """メイン処理"""

    print("=" * 60)
    print("PT向け論文サマリー自動生成ツール")
    print("=" * 60)
    print()
    print("論文テキストを以下の形式で入力してください：")
    print("  [論文1のテキスト]")
    print("  ---")
    print("  [論文2のテキスト]")
    print("  ---")
    print("  ...")
    print()
    print("入力終了: Ctrl+D (Linux/Mac) または Ctrl+Z + Enter (Windows)")
    print("=" * 60)
    print()

    # 標準入力から全テキストを読み込み
    try:
        input_text = sys.stdin.read()
    except KeyboardInterrupt:
        print("\n中止しました。")
        sys.exit(0)

    if not input_text.strip():
        print("エラー: テキストが入力されていません")
        sys.exit(1)

    # 「---」で論文を分割
    papers = [p.strip() for p in input_text.split("---") if p.strip()]

    if not papers:
        print("エラー: 有効な論文テキストが見つかりません")
        sys.exit(1)

    print(f"\n{len(papers)}件の論文が検出されました。処理を開始します...\n")

    # Claude APIクライアント初期化
    api_key = get_api_key()
    client = Anthropic(api_key=api_key)

    # サマリー生成
    summaries = []
    for idx, paper in enumerate(papers, 1):
        print(f"[{idx}/{len(papers)}] 論文を処理中...", end="", flush=True)
        try:
            summary = generate_pt_summary(client, paper)
            summaries.append(summary)
            print(" ✓")
        except Exception as e:
            print(f" ✗ エラー: {e}")
            sys.exit(1)

    # RAS_IMPORT_BOX に保存
    ras_box = Path(r"C:\Users\yuuna\agens\RAS_IMPORT_BOX")
    ras_box.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = ras_box / f"papers_summary_{timestamp}.md"

    # H1見出しで区切られたMarkdownを生成
    output_content = "\n\n".join(summaries)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_content)

    print()
    print("=" * 60)
    print(f"✓ サマリー生成完了")
    print(f"  保存先: {output_file}")
    print()
    print("次のステップ:")
    print(f"  python C:\\Users\\yuuna\\agens\\knowledge\\import_research.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
