"""アプリケーション設定管理"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 5050))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    # LLM 設定
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_MODE = "openai" if OPENAI_API_KEY else "mock"

    # データ保存パス
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
    HISTORY_DIR = os.path.join(DATA_DIR, "history")

    @classmethod
    def ensure_dirs(cls):
        """必要なディレクトリを作成"""
        for d in [cls.DATA_DIR, cls.SESSIONS_DIR, cls.HISTORY_DIR]:
            os.makedirs(d, exist_ok=True)
