"""Prompt Generator Studio - メインアプリケーション"""
import json
import os
import sys
import uuid

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from core.session_manager import SessionManager
from core.conversation import ConversationEngine
from core.state_schema import SessionState
from prompt_generators.prompt_engine import PromptEngine
from prompt_generators.presets import (
    PURPOSE_PRESETS, ASPECT_RATIO_PRESETS, STRUCTURE_PRESETS,
    STYLE_PRESETS, GENRE_PRESETS, OUTPUT_FORMAT
)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# サービス初期化
Config.ensure_dirs()
session_mgr = SessionManager()
conversation = ConversationEngine()
prompt_engine = PromptEngine()

# アップロード用ディレクトリ
UPLOAD_DIR = os.path.join(Config.DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# ページルート
# ============================================================

@app.route("/")
def index():
    """メイン画面"""
    return render_template("index.html")


# ============================================================
# プリセットAPI
# ============================================================

@app.route("/api/presets", methods=["GET"])
def get_all_presets():
    """全プリセットデータを返す"""
    return jsonify({
        "purpose": PURPOSE_PRESETS,
        "aspect_ratio": ASPECT_RATIO_PRESETS,
        "structure": STRUCTURE_PRESETS,
        "style": STYLE_PRESETS,
        "genre": GENRE_PRESETS,
        "output_format": OUTPUT_FORMAT,
    })


# ============================================================
# プロンプト生成 API
# ============================================================

@app.route("/api/generate", methods=["POST"])
def generate_prompts():
    """プロンプトを生成"""
    data = request.get_json()

    config = {
        "purpose": data.get("purpose", "carousel"),
        "aspect_ratio": data.get("aspect_ratio", "1:1"),
        "count": int(data.get("count", 1)),
        "genre": data.get("genre", "business"),
        "genre_custom": data.get("genre_custom", ""),
        "structure": data.get("structure", "infographic"),
        "style": data.get("style", "anime"),
        "output_format": data.get("output_format", "individual"),
        "slides": data.get("slides", []),
        "character": data.get("character", {}),
    }

    try:
        result = prompt_engine.generate(config)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# チャット API（会話エンジンはそのまま）
# ============================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """チャットメッセージを処理"""
    data = request.get_json()
    user_text = data.get("message", "").strip()
    session_id = data.get("session_id", "")

    if not user_text:
        return jsonify({"error": "メッセージが空です"}), 400

    # セッション取得 or 新規作成
    state = None
    if session_id:
        state = session_mgr.load_session(session_id)
    if not state:
        state = session_mgr.create_session()

    # 会話処理
    result = conversation.process_input(state, user_text)

    # AI応答をメッセージに追加
    state.add_message("assistant", result["response"])

    # セッション保存
    session_mgr.save_session(state)

    return jsonify({
        "session_id": state.session_id,
        "response": result["response"],
        "mode": state.mode,
        "state_summary": state.get_summary(),
    })


# ============================================================
# セッション API
# ============================================================

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    """セッション一覧"""
    sessions = session_mgr.list_sessions()
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """セッション詳細"""
    state = session_mgr.load_session(session_id)
    if not state:
        return jsonify({"error": "セッションが見つかりません"}), 404
    return jsonify(state.to_dict())


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """セッション削除"""
    success = session_mgr.delete_session(session_id)
    return jsonify({"success": success})


# ============================================================
# 画像アップロード API
# ============================================================

@app.route("/api/upload", methods=["POST"])
def upload_image():
    """キャラクター参照画像のアップロード"""
    if 'file' not in request.files:
        return jsonify({"error": "ファイルがありません"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "ファイル名がありません"}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        return jsonify({
            "success": True,
            "filename": filename,
            "url": f"/uploads/{filename}"
        })

    return jsonify({"error": "許可されていないファイル形式です"}), 400


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """アップロード画像の配信"""
    return send_from_directory(UPLOAD_DIR, filename)


# ============================================================
# エクスポート API
# ============================================================

@app.route("/api/export/prompts", methods=["POST"])
def export_prompts():
    """生成済みプロンプトをまとめてエクスポート"""
    data = request.get_json()
    prompts = data.get("prompts", [])
    output_format = data.get("output_format", "individual")
    grid_prompt = data.get("grid_prompt", None)

    # テキストファイル形式で出力
    lines = []
    lines.append("=" * 60)
    lines.append("  Prompt Generator Studio - Export")
    lines.append("=" * 60)
    lines.append("")

    if output_format == "grid" and grid_prompt:
        lines.append("## Grid Output (1 image)")
        lines.append("")
        lines.append("[NANOBANANA2 - Positive]")
        lines.append(grid_prompt.get("nb2_positive", ""))
        lines.append("")
        lines.append("[NANOBANANA2 - Negative]")
        lines.append(grid_prompt.get("nb2_negative", ""))
        lines.append("")
        lines.append("[Midjourney]")
        lines.append(grid_prompt.get("midjourney", ""))
        lines.append("")
        lines.append("[Stable Diffusion - Positive]")
        lines.append(grid_prompt.get("sd_positive", ""))
        lines.append("")
        lines.append("[Stable Diffusion - Negative]")
        lines.append(grid_prompt.get("sd_negative", ""))
        lines.append("")
        lines.append("[DALL-E]")
        lines.append(grid_prompt.get("dalle", ""))
        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    for p in prompts:
        title = p.get('title') or f"Image {p.get('index', 0) + 1}"
        lines.append(f"## {title}")
        lines.append("")
        lines.append("[NANOBANANA2 - Positive]")
        lines.append(p.get("nb2_positive", ""))
        lines.append("")
        lines.append("[NANOBANANA2 - Negative]")
        lines.append(p.get("nb2_negative", ""))
        lines.append("")
        lines.append("[Midjourney]")
        lines.append(p.get("midjourney", ""))
        lines.append("")
        lines.append("[Stable Diffusion - Positive]")
        lines.append(p.get("sd_positive", ""))
        lines.append("")
        lines.append("[Stable Diffusion - Negative]")
        lines.append(p.get("sd_negative", ""))
        lines.append("")
        settings = p.get("sd_settings", {})
        if settings:
            lines.append(f"[SD Settings] {settings.get('width')}x{settings.get('height')}, "
                        f"Steps: {settings.get('steps')}, CFG: {settings.get('cfg_scale')}, "
                        f"Sampler: {settings.get('sampler')}, Model: {settings.get('model')}")
        lines.append("")
        lines.append("[DALL-E]")
        lines.append(p.get("dalle", ""))
        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    content = "\n".join(lines)
    return content, 200, {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": "attachment; filename=prompts_export.txt"
    }


# ============================================================
# メイン
# ============================================================

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    print("=" * 60)
    print("  Prompt Generator Studio")
    print(f"  URL: http://{Config.HOST}:{Config.PORT}")
    print("=" * 60)
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
