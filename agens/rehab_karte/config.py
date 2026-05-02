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

# 期限警告の閾値（日）
DEADLINE_WARNING_DAYS = 14
