"""セッション管理"""
import json
import os
import time
import shutil
from typing import Optional
from config import Config
from core.state_schema import SessionState


class SessionManager:
    """セッションの保存・読み込み・一覧管理"""

    def __init__(self):
        Config.ensure_dirs()

    def create_session(self) -> SessionState:
        """新規セッション作成"""
        state = SessionState()
        self.save_session(state)
        return state

    def save_session(self, state: SessionState):
        """セッションをファイルに保存"""
        filepath = os.path.join(Config.SESSIONS_DIR, f"{state.session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(state.to_json())

    def load_session(self, session_id: str) -> Optional[SessionState]:
        """セッションを読み込み"""
        filepath = os.path.join(Config.SESSIONS_DIR, f"{session_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return SessionState.from_json(f.read())

    def list_sessions(self) -> list:
        """セッション一覧を返す"""
        sessions = []
        if not os.path.exists(Config.SESSIONS_DIR):
            return sessions

        for filename in os.listdir(Config.SESSIONS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(Config.SESSIONS_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.loads(f.read())
                    sessions.append({
                        "session_id": data.get("session_id", ""),
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "summary": SessionState.from_dict(data).get_summary(),
                        "message_count": len(data.get("messages", []))
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """セッション削除"""
        filepath = os.path.join(Config.SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def save_version(self, state: SessionState):
        """バージョン履歴を保存"""
        version_dir = os.path.join(Config.HISTORY_DIR, state.session_id)
        os.makedirs(version_dir, exist_ok=True)

        filepath = os.path.join(version_dir, f"v{state.version}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(state.to_json())

    def get_version_history(self, session_id: str) -> list:
        """バージョン履歴一覧"""
        version_dir = os.path.join(Config.HISTORY_DIR, session_id)
        if not os.path.exists(version_dir):
            return []

        versions = []
        for filename in sorted(os.listdir(version_dir)):
            if filename.endswith(".json"):
                versions.append(filename.replace(".json", ""))
        return versions

    def load_version(self, session_id: str, version: str) -> Optional[SessionState]:
        """特定バージョンを読み込み"""
        filepath = os.path.join(Config.HISTORY_DIR, session_id, f"{version}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return SessionState.from_json(f.read())
