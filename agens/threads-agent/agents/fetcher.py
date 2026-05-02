"""
Fetcher Agent
- Reads post_history.json
- Fetches metrics at 3 checkpoints after posting:
    1h  : 0.5 - 2h   (初速チェック - バズの兆候)
    6h  : 5  - 8h    (中間計測)
    24h : 20 - 28h   (最終計測)
- Calls Threads API to get metrics (views, likes, replies, reposts, quotes)
- Updates post_history.json with metrics_1h, metrics_6h, metrics_24h
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class FetcherAgent:
    def __init__(self, config, data_dir):
        self.config = config
        self.data_dir = Path(data_dir)
        self.access_token = getattr(config, "THREADS_ACCESS_TOKEN", None)
        self.base_url = getattr(config, "THREADS_BASE_URL", "https://graph.threads.net/v1.0")

    def _load_json(self, path, default):
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_post_history(self):
        return self._load_json(self.data_dir / "post_history.json", [])

    def _save_post_history(self, history):
        self._save_json(self.data_dir / "post_history.json", history)

    # Checkpoints: (key, label, min_hours, max_hours)
    CHECKPOINTS = [
        ("metrics_1h",  "1h",  0.5,  2.0),
        ("metrics_6h",  "6h",  5.0,  8.0),
        ("metrics_24h", "24h", 20.0, 28.0),
    ]

    def _get_pending_checkpoints(self, post):
        """
        Returns list of checkpoint tuples that are due but not yet fetched.
        """
        if post.get("status") != "posted":
            return []
        if not post.get("threads_post_id"):
            return []

        posted_at_str = post.get("posted_at")
        if not posted_at_str:
            return []

        try:
            posted_at = datetime.fromisoformat(posted_at_str)
        except ValueError:
            return []

        now = datetime.utcnow()
        hours_since = (now - posted_at).total_seconds() / 3600

        due = []
        for key, label, min_h, max_h in self.CHECKPOINTS:
            already_fetched = bool(post.get(f"{key}_fetched_at"))
            in_window = min_h <= hours_since <= max_h
            if in_window and not already_fetched:
                due.append((key, label))
        return due

    def _fetch_metrics_api(self, post_id):
        """
        Fetch metrics for a post from Threads API.
        Returns dict with views, likes, replies, reposts, quotes or None on error.
        """
        url = f"{self.base_url}/{post_id}/insights"
        params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": self.access_token,
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            metrics = {}
            for item in data.get("data", []):
                name = item.get("name")
                # Threads API returns values[0].value for lifetime metrics
                values = item.get("values", [])
                value = values[0].get("value", 0) if values else item.get("total_value", {}).get("value", 0)
                if name:
                    metrics[name] = value

            return metrics
        except requests.RequestException as e:
            logger.error(f"FetcherAgent: API error for post {post_id}: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def _mock_metrics(self, post_id):
        """Generate mock metrics when no API credentials available."""
        import random
        views = random.randint(50, 5000)
        like_rate = random.uniform(0.01, 0.08)
        reply_rate = random.uniform(0.005, 0.03)
        repost_rate = random.uniform(0.002, 0.015)
        quote_rate = random.uniform(0.001, 0.01)

        metrics = {
            "views": views,
            "likes": int(views * like_rate),
            "replies": int(views * reply_rate),
            "reposts": int(views * repost_rate),
            "quotes": int(views * quote_rate),
        }
        logger.info(f"FetcherAgent [MOCK]: Generated mock metrics for {post_id}: {metrics}")
        return metrics

    def run(self):
        """
        Main run method.
        Fetches metrics at 1h, 6h, 24h checkpoints for eligible posts.
        Returns list of (post, checkpoint_label) tuples that were updated.
        """
        logger.info("FetcherAgent: Starting run (checkpoints: 1h / 6h / 24h)")

        has_credentials = bool(self.access_token)
        if not has_credentials:
            logger.warning("FetcherAgent: No Threads API credentials. Running in mock mode.")

        history = self._load_post_history()
        updated = []

        for i, post in enumerate(history):
            checkpoints = self._get_pending_checkpoints(post)
            if not checkpoints:
                continue

            post_id = post.get("threads_post_id")
            for key, label in checkpoints:
                logger.info(
                    f"FetcherAgent: [{label}] Fetching metrics for post "
                    f"{post_id} (internal: {post.get('id', '')[:8]})"
                )

                metrics = (
                    self._fetch_metrics_api(post_id)
                    if has_credentials
                    else self._mock_metrics(post_id)
                )

                if metrics is not None:
                    history[i][key] = metrics
                    history[i][f"{key}_fetched_at"] = datetime.now().isoformat()
                    updated.append((history[i], label))
                    logger.info(f"FetcherAgent: [{label}] {post_id}: {metrics}")
                else:
                    logger.warning(f"FetcherAgent: [{label}] Could not fetch metrics for {post_id}.")

        self._save_post_history(history)
        logger.info(f"FetcherAgent: Updated {len(updated)} checkpoint(s).")
        return updated
