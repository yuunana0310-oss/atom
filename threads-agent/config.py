"""
Configuration module for Threads automation system.
Loads from environment variables with fallback to None (mock mode).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
# override=True: Windows の環境変数が空文字で設定されている場合に上書きするため必須
load_dotenv(override=True)

# === API Credentials (account1 default) ===
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# === Posting Limits ===
# アカウントごとに最大10件/日。最低間隔1時間を厳守してbot判定を回避する。
MAX_DAILY_POSTS = 10
MIN_POST_INTERVAL_HOURS = 1
QUALITY_SCORE_THRESHOLD = 7.0
SIMILARITY_THRESHOLD = 0.85
MAX_RETRIES = 3

# === Time Slots (24h format) ===
# 医療職のゴールデンタイムに最適化（views低下対策）
# 朝6時台：出勤準備・通勤中のアクティブタイム
# 夜19-21時：帰宅後のリラックスタイム
TIME_SLOTS = [
    "06:30",  # 朝（出勤準備）
    "07:00",  # 朝（通勤中）
    "07:30",  # 朝（通勤中）
    "19:00",  # 夜（帰宅直後）
    "19:45",  # 夜（リラックス開始）
    "20:30",  # 夜（ゴールデンタイム中盤）
    "21:00",  # 夜（ゴールデンタイム終盤）
    "21:45",  # 夜（最終段階）
    "23:00",  # 夜更かし層
    "00:30"   # 深夜（本当の夜更かし層）
]

# === Directories ===
BASE_DIR = Path(__file__).parent
AGENTS_DIR = BASE_DIR / "agents"
KNOWLEDGE_DIR = BASE_DIR / "knowledge" / "account1"
DATA_DIR = BASE_DIR / "data" / "account1"

# === File Paths ===
ACCOUNT_PROFILE_PATH = KNOWLEDGE_DIR / "account_profile.json"
POST_PATTERNS_PATH = KNOWLEDGE_DIR / "post_patterns.json"
THEME_TREE_PATH = KNOWLEDGE_DIR / "theme_tree.json"
NG_WORDS_PATH = KNOWLEDGE_DIR / "ng_words.json"

POST_HISTORY_PATH = DATA_DIR / "post_history.json"
QUEUE_PATH = DATA_DIR / "queue.json"
DRAFTS_PATH = DATA_DIR / "drafts.json"
RESEARCH_CACHE_PATH = DATA_DIR / "research_cache.json"
FEEDBACK_PATH = DATA_DIR / "feedback_instructions.json"
ERROR_LOG_PATH = DATA_DIR / "error_log.json"
SUPERVISOR_STATE_PATH = DATA_DIR / "supervisor_state.json"
KILL_SWITCH_PATH = DATA_DIR / "KILL_SWITCH"

# === Operation Mode ===
# "auto"   : posts go directly to queue after scoring (0% human)
# "review" : posts go to drafts.json, human approves before queuing (5% human)
OPERATION_MODE = os.getenv("OPERATION_MODE", "auto")

# === API Endpoints ===
THREADS_BASE_URL = "https://graph.threads.net/v1.0"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# === Model Settings ===
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# === Logging ===
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def switch_account(account_id: str):
    """
    Switch all account-dependent paths and credentials to the specified account.
    Call this before building agents.

    Supported accounts: "account1", "account2", "account3"
    """
    global KNOWLEDGE_DIR, DATA_DIR
    global ACCOUNT_PROFILE_PATH, POST_PATTERNS_PATH, THEME_TREE_PATH, NG_WORDS_PATH
    global POST_HISTORY_PATH, QUEUE_PATH, DRAFTS_PATH, RESEARCH_CACHE_PATH
    global FEEDBACK_PATH, ERROR_LOG_PATH, SUPERVISOR_STATE_PATH, KILL_SWITCH_PATH
    global THREADS_ACCESS_TOKEN, THREADS_USER_ID

    KNOWLEDGE_DIR = BASE_DIR / "knowledge" / account_id
    DATA_DIR = BASE_DIR / "data" / account_id

    ACCOUNT_PROFILE_PATH = KNOWLEDGE_DIR / "account_profile.json"
    POST_PATTERNS_PATH = KNOWLEDGE_DIR / "post_patterns.json"
    THEME_TREE_PATH = KNOWLEDGE_DIR / "theme_tree.json"
    NG_WORDS_PATH = KNOWLEDGE_DIR / "ng_words.json"

    POST_HISTORY_PATH = DATA_DIR / "post_history.json"
    QUEUE_PATH = DATA_DIR / "queue.json"
    DRAFTS_PATH = DATA_DIR / "drafts.json"
    RESEARCH_CACHE_PATH = DATA_DIR / "research_cache.json"
    FEEDBACK_PATH = DATA_DIR / "feedback_instructions.json"
    ERROR_LOG_PATH = DATA_DIR / "error_log.json"
    SUPERVISOR_STATE_PATH = DATA_DIR / "supervisor_state.json"
    KILL_SWITCH_PATH = DATA_DIR / "KILL_SWITCH"

    # アカウント別のTokenを読み込む（account1はデフォルト、account2はサフィックス_2）
    suffix = "" if account_id == "account1" else f"_{account_id.upper()}"
    THREADS_ACCESS_TOKEN = os.getenv(f"THREADS_ACCESS_TOKEN{suffix}")
    THREADS_USER_ID = os.getenv(f"THREADS_USER_ID{suffix}")


def check_api_keys(account_id: str = None):
    """Returns dict of which API keys are available.
    Reads directly from env to avoid race conditions with switch_account().
    """
    if account_id and account_id != "account1":
        suffix = f"_{account_id.upper()}"
        token = os.getenv(f"THREADS_ACCESS_TOKEN{suffix}")
        user_id = os.getenv(f"THREADS_USER_ID{suffix}")
    else:
        token = os.getenv("THREADS_ACCESS_TOKEN")
        user_id = os.getenv("THREADS_USER_ID")
    return {
        "threads": bool(token and user_id),
        "youtube": bool(YOUTUBE_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
    }
