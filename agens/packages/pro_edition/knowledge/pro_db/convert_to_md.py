"""
PDF / Word → Markdown 自動変換＆DB登録ツール
=============================================
使い方:
  1. このファイルと同じフォルダに「input」フォルダを作成する
  2. 変換したいPDF・Word（.docx）を「input」フォルダに入れる
  3. このファイルをダブルクリック（または python convert_to_md.py で実行）
  4. 「knowledge/pro_db/」に自動でMarkdownが保存され、AIデータベースに登録完了！

必要なライブラリのインストール（初回のみ）:
  pip install pdfminer.six python-docx
"""

import os
import sys
import re

# --- 必要ライブラリの自動チェック ---
def check_and_install(package_name, import_name=None):
    import_name = import_name or package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"[SETUP] 必要なライブラリ「{package_name}」を自動インストール中...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "-q"])
        print(f"[SETUP] インストール完了: {package_name}")

check_and_install("pdfminer.six", "pdfminer")
check_and_install("python-docx", "docx")

# --- メインのインポート ---
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document

# --- 設定 ---
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR   = os.path.join(BASE_DIR, "input")
OUTPUT_DIR  = os.path.join(BASE_DIR, "..", "pro_db")  # knowledge/pro_db/ に直接保存
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------------------
def sanitize_filename(name: str) -> str:
    """ファイル名に使えない文字を除去する"""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name[:50]

def text_to_markdown(text: str, source_name: str) -> str:
    """抽出したテキストをMarkdown形式に変換する"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    md_lines = [
        f"---",
        f"title: {source_name}",
        f"source: 社内資料（自動変換）",
        f"---",
        "",
        f"# {source_name}",
        "",
    ]
    for line in lines:
        # 短すぎる行は見出し候補として扱う
        if len(line) < 30 and not line.endswith(('。', '、', '.', ',')):
            md_lines.append(f"\n## {line}\n")
        else:
            md_lines.append(line)
    return "\n".join(md_lines)

def convert_pdf(filepath: str) -> str:
    """PDFからテキストを抽出する"""
    print(f"  [PDF] テキスト抽出中: {os.path.basename(filepath)}")
    try:
        text = pdf_extract_text(filepath)
        if not text or len(text.strip()) < 50:
            return ""
        return text
    except Exception as e:
        print(f"  [ERROR] PDF変換エラー: {e}")
        return ""

def convert_docx(filepath: str) -> str:
    """Wordファイルからテキストを抽出する"""
    print(f"  [Word] テキスト抽出中: {os.path.basename(filepath)}")
    try:
        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"  [ERROR] Word変換エラー: {e}")
        return ""

def process_all():
    files = [f for f in os.listdir(INPUT_DIR)
             if f.lower().endswith(('.pdf', '.docx', '.doc'))]

    if not files:
        print(f"\n[INFO] 「input」フォルダにPDFまたはWordファイルが見つかりませんでした。")
        print(f"       変換したいファイルを以下のフォルダに入れてから再実行してください:")
        print(f"       → {INPUT_DIR}")
        return 0

    converted = 0
    skipped   = 0

    for filename in files:
        filepath    = os.path.join(INPUT_DIR, filename)
        source_name = os.path.splitext(filename)[0]
        out_name    = f"doc_{sanitize_filename(source_name)}.md"
        out_path    = os.path.join(OUTPUT_DIR, out_name)

        if os.path.exists(out_path):
            print(f"  [SKIP] すでに変換済みです: {filename}")
            skipped += 1
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            text = convert_pdf(filepath)
        elif ext in (".docx", ".doc"):
            text = convert_docx(filepath)
        else:
            continue

        if not text:
            print(f"  [WARN] テキストを抽出できませんでした（スキャンPDF等）: {filename}")
            continue

        md_content = text_to_markdown(text, source_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"  [OK] 変換・保存完了: {filename} → {out_name}")
        converted += 1

    return converted

# ----------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("  PDF / Word → Markdown 変換ツール")
    print("=" * 55)
    print(f"\n変換元フォルダ: {INPUT_DIR}")
    print(f"保存先フォルダ:  {OUTPUT_DIR}")
    print()

    count = process_all()

    if count > 0:
        print(f"\n[SUCCESS] {count}件のファイルをMarkdownに変換しました！")
        print("\n次に、AIのデータベース（RAG）を更新します...")
        try:
            sys.path.insert(0, OUTPUT_DIR)
            from pro_rag_engine import ProRAG
            rag = ProRAG()
            rag.index()
            print("[SUCCESS] AIの脳への学習が完了しました！")
            print("          さっそくAI社員に質問してみてください。")
        except Exception as e:
            print(f"[WARN] RAGへの自動登録はスキップされました: {e}")
            print("       手動で pro_rag_engine.py を実行してください。")
    elif count == 0:
        print("\n新しく変換されたファイルはありませんでした。")

    print("\n" + "=" * 55)
    input("Enterキーを押すと終了します...")
