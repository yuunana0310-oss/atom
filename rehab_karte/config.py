import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "rehab.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

# .env からAPIキーを読み込む（python-dotenv 不要・手動パース）
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

APP_TITLE = "リハビリカルテ"
WINDOW_SIZE = "1200x750"

# customtkinter テーマ
CTK_APPEARANCE = "light"   # "light" or "dark"
CTK_THEME = "blue"         # "blue" / "green" / "dark-blue"

# デザイン・カラートークン (Premium Modern Palette)
COLORS = {
    "sidebar_bg": "#FFFFFF",
    "sidebar_hover": "#F8FAFC",
    "active_nav": "#E0F2FE",   # アクティブなメニューの背景
    "active_text": "#005BC5",  # アクティブなメニューの文字色
    "primary": "#0F172A",      # Slate 900 (サイドバー背景、主要タイトル)
    "secondary": "#334155",    # Slate 700
    "accent": "#0284C7",       # Sky 600
    "warning": "#F59E0B",      # Amber 500
    "danger": "#EF4444",       # Red 500
    "success": "#10B981",      # Emerald 500
    "bg_light": "#EDF2F7",     # 全体背景
    "card_bg": "#FFFFFF",      # カード背景
    "text_main": "#1E293B",    # メイン文字色
    "text_sub": "#64748B",     # 補助文字色
}

FONT_FAMILY = ("Yu Gothic UI", "Inter", "Segoe UI", "Meiryo")

# 期限警告の閾値（日）
DEADLINE_WARNING_DAYS = 14
