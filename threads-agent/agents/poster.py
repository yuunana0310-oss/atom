"""
Poster Agent
- Reads queue.json for posts with status='queued'
- Checks time slots - only posts during scheduled slots (within ±15 min window)
- Checks that last post was >= MIN_POST_INTERVAL_HOURS ago
- Posts via Threads API
- For comment_hook type: posts main content, then replies in comments
- For affiliate posts: adds affiliate_comment as reply
- Updates post_history.json with threads_post_id
- Max MAX_DAILY_POSTS per day
"""
import json
import logging
import os
import shutil
import time
from datetime import datetime, date
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class PosterAgent:
    def __init__(self, config, data_dir):
        self.config = config
        self.data_dir = Path(data_dir)
        self.access_token = getattr(config, "THREADS_ACCESS_TOKEN", None)
        self.user_id = getattr(config, "THREADS_USER_ID", None)
        self.base_url = getattr(config, "THREADS_BASE_URL", "https://graph.threads.net/v1.0")
        self.time_slots = getattr(config, "TIME_SLOTS", [])
        self.max_daily_posts = getattr(config, "MAX_DAILY_POSTS", 10)
        self.min_interval_hours = getattr(config, "MIN_POST_INTERVAL_HOURS", 1)

    def _load_json(self, path, default):
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_json(self, path, data):
        """Write JSON atomically via a temporary file to prevent corruption on concurrent writes."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # Atomic on same drive (Windows + POSIX)

    def _load_queue(self):
        return self._load_json(self.data_dir / "queue.json", [])

    def _save_queue(self, queue):
        """Save queue.json atomically and keep queue.json.bak as a rolling backup."""
        queue_path = self.data_dir / "queue.json"
        bak_path = self.data_dir / "queue.json.bak"
        # Back up the current (healthy) queue before overwriting
        if queue_path.exists():
            shutil.copy2(queue_path, bak_path)
        self._save_json(queue_path, queue)

    def _load_post_history(self):
        return self._load_json(self.data_dir / "post_history.json", [])

    def _save_post_history(self, history):
        self._save_json(self.data_dir / "post_history.json", history)

    def _is_within_time_slot(self, now=None, window_minutes=15):
        """Returns True if current time is within window_minutes of any time slot."""
        if not self.time_slots:
            return True  # No slots configured, always OK

        if now is None:
            now = datetime.now()

        current_minutes = now.hour * 60 + now.minute

        for slot in self.time_slots:
            try:
                h, m = map(int, slot.split(":"))
                slot_minutes = h * 60 + m
                diff = abs(current_minutes - slot_minutes)
                # Handle midnight wrap-around
                diff = min(diff, 1440 - diff)
                if diff <= window_minutes:
                    return True
            except (ValueError, AttributeError):
                continue

        return False

    def _get_posts_today(self, history):
        """Count posts made today from post_history."""
        today = date.today().isoformat()
        return [
            p for p in history
            if p.get("posted_at", "").startswith(today) and p.get("status") == "posted"
        ]

    def _get_last_post_time(self, history):
        """Return datetime of most recent post, or None."""
        posted = [p for p in history if p.get("status") == "posted" and p.get("posted_at")]
        if not posted:
            return None
        posted.sort(key=lambda p: p["posted_at"], reverse=True)
        try:
            return datetime.fromisoformat(posted[0]["posted_at"])
        except (ValueError, KeyError):
            return None

    def _minutes_since_last_post(self, history):
        """Return minutes since last post, or None if no posts."""
        last_time = self._get_last_post_time(history)
        if last_time is None:
            return None
        delta = datetime.now() - last_time
        return delta.total_seconds() / 60

    def _create_threads_media(self, text, reply_to_id=None, media_url=None):
        """
        Create a Threads media container.
        Returns the creation_id or None on failure.
        """
        url = f"{self.base_url}/{self.user_id}/threads"
        params = {
            "media_type": "IMAGE" if media_url else "TEXT",
            "text": text,
            "access_token": self.access_token,
        }
        if media_url:
            params["image_url"] = media_url
        if reply_to_id:
            params["reply_to_id"] = reply_to_id

        try:
            resp = requests.post(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("id")
        except requests.RequestException as e:
            logger.error(f"PosterAgent: Failed to create media container: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def _publish_threads_media(self, creation_id):
        """
        Publish a Threads media container.
        Returns the post ID or None on failure.
        """
        url = f"{self.base_url}/{self.user_id}/threads_publish"
        params = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }

        try:
            resp = requests.post(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("id")
        except requests.RequestException as e:
            logger.error(f"PosterAgent: Failed to publish media: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def _post_text(self, text, reply_to_id=None, media_url=None):
        """
        Post text to Threads (create + publish).
        Returns the published post ID or None.
        """
        creation_id = self._create_threads_media(text, reply_to_id=reply_to_id, media_url=media_url)
        if not creation_id:
            return None

        # Threads recommends a short delay between create and publish
        time.sleep(2)

        post_id = self._publish_threads_media(creation_id)
        return post_id

    def _mock_post(self, text, reply_to_id=None, media_url=None):
        """Simulate posting when no API credentials are available."""
        import uuid
        mock_id = f"mock_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"PosterAgent [MOCK]: Would post text ({len(text)} chars)"
            f"{' with image' if media_url else ''}. Mock ID: {mock_id}"
        )
        logger.debug(f"PosterAgent [MOCK] content:\n{text[:200]}...")
        return mock_id

    def _get_scheduled_due(self, queue):
        """Return queued items whose scheduled_at has passed."""
        now = datetime.now()
        due = []
        for p in queue:
            if p.get("status") != "queued":
                continue
            sa = p.get("scheduled_at")
            if not sa:
                continue
            try:
                if datetime.fromisoformat(sa) <= now:
                    due.append(p)
            except (ValueError, TypeError):
                pass
        return sorted(due, key=lambda x: x.get("scheduled_at", ""))

    def run(self, force=False):
        """
        Main run method.
        Posts queued items according to schedule.

        Priority:
          1. Items with scheduled_at <= now  → bypass slot + interval checks
          2. Items with no scheduled_at      → bypass slot check, interval enforced
          3. Items with future scheduled_at  → obey slot + interval checks

        force=True: skip time slot check for priority-3 items (interval always enforced)
        Returns list of posted items.
        """
        logger.info(f"PosterAgent: Starting run (force={force})")

        # --- 多重起動防止ロック ---
        # .poster.lock が存在する場合は別プロセスがすでに実行中と判断してスキップする。
        # try/finally で正常終了・例外終了のどちらでも必ずロックを解放する。
        lock_path = self.data_dir / ".poster.lock"
        if lock_path.exists():
            logger.warning(
                f"PosterAgent: Lock file exists ({lock_path}). "
                "Another process is already running. Exiting to prevent duplicate posts."
            )
            return []
        try:
            lock_path.write_text(
                f"pid={os.getpid()} started={datetime.now().isoformat()}", encoding="utf-8"
            )
            return self._run_inner(force=force)
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass

    def _run_inner(self, force=False):
        """Actual run logic, called only when the lock is held."""

        has_credentials = bool(self.access_token and self.user_id)
        if not has_credentials:
            logger.warning("PosterAgent: No Threads API credentials. Running in mock mode.")

        queue = self._load_queue()
        history = self._load_post_history()

        # --- 残留 'posting' アイテムの回収 ---
        # プロセスがクラッシュ等で途中終了した場合、status が 'posting' のまま
        # 残留することがある。POSTING_TIMEOUT_MINUTES 以上経過していれば
        # 'queued' に差し戻して再試行対象とする。
        POSTING_TIMEOUT_MINUTES = 5
        now_dt = datetime.now()
        stale_recovered = 0
        for q in queue:
            if q.get("status") != "posting":
                continue
            started_at_str = q.get("posting_started_at")
            if not started_at_str:
                q["status"] = "queued"
                stale_recovered += 1
                continue
            try:
                elapsed = (now_dt - datetime.fromisoformat(started_at_str)).total_seconds() / 60
                if elapsed >= POSTING_TIMEOUT_MINUTES:
                    logger.warning(
                        f"PosterAgent: [{q['id'][:8]}] stuck in 'posting' for "
                        f"{elapsed:.1f} min — resetting to 'queued'."
                    )
                    q["status"] = "queued"
                    q.pop("posting_started_at", None)
                    stale_recovered += 1
            except (ValueError, TypeError):
                q["status"] = "queued"
                stale_recovered += 1
        if stale_recovered:
            self._save_queue(queue)

        # Check daily post limit
        posts_today = self._get_posts_today(history)
        if len(posts_today) >= self.max_daily_posts:
            logger.info(
                f"PosterAgent: Daily limit reached ({len(posts_today)}/{self.max_daily_posts}). "
                "No more posts today."
            )
            return []

        # All queued items（'posting' は別プロセスが処理中のため除外）
        queued = [p for p in queue if p.get("status") == "queued"]
        if not queued:
            logger.info("PosterAgent: No queued posts.")
            return []

        # --- 重複IDの排除（同一IDが複数キューに入っていた場合は最初の1件のみ残す）---
        seen_ids = set()
        deduped = []
        for p in queued:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                deduped.append(p)
            else:
                logger.warning(f"PosterAgent: Duplicate queue entry [{p['id'][:8]}] — skipping.")
                for q in queue:
                    if q["id"] == p["id"] and q is not p:
                        q["status"] = "failed"
                        q["failed_at"] = datetime.now().isoformat()
        if len(deduped) < len(queued):
            self._save_queue(queue)
        queued = deduped

        # --- 投稿済みIDの再投稿を防止 ---
        posted_ids = {p.get("id") for p in history if p.get("status") == "posted"}
        already_posted = [p for p in queued if p["id"] in posted_ids]
        for p in already_posted:
            logger.warning(f"PosterAgent: [{p['id'][:8]}] already in post_history — removing from queue.")
            for q in queue:
                if q["id"] == p["id"]:
                    q["status"] = "posted"
        if already_posted:
            self._save_queue(queue)
            queued = [p for p in queued if p["id"] not in posted_ids]

        # --- Priority 1: scheduled_at が期限切れのアイテム ---
        # タイムスロット・インターバルチェックをスキップして即時投稿
        scheduled_due = self._get_scheduled_due(queued)

        # --- Priority 2: scheduled_at なしのアイテム ---
        # タイムスロットチェックをスキップし、インターバルチェックのみ実施
        normal_queued = [p for p in queued if not p.get("scheduled_at")]

        if scheduled_due:
            to_post = [scheduled_due[0]]
            logger.info(
                f"PosterAgent: Scheduled post due [{to_post[0]['id'][:8]}] "
                f"scheduled_at={to_post[0].get('scheduled_at')} — bypassing slot/interval checks."
            )
        elif normal_queued:
            # Check minimum interval（スロットチェックは不要）
            minutes_since = self._minutes_since_last_post(history)
            min_interval_minutes = self.min_interval_hours * 60
            if minutes_since is not None and minutes_since < min_interval_minutes:
                logger.info(
                    f"PosterAgent: Last post was {minutes_since:.1f} minutes ago. "
                    f"Minimum interval is {min_interval_minutes} minutes. Skipping."
                )
                return []
            to_post = normal_queued[:1]
            logger.info(
                f"PosterAgent: Normal queued post [{to_post[0]['id'][:8]}] "
                "— bypassing slot check, interval OK."
            )
        else:
            # scheduled_at ありだがまだ時刻未到達のアイテムのみ残っている場合
            # タイムスロット＋インターバルチェックを通常通り実施
            if not force and not self._is_within_time_slot():
                logger.info("PosterAgent: Not within any time slot window. Skipping.")
                return []

            minutes_since = self._minutes_since_last_post(history)
            min_interval_minutes = self.min_interval_hours * 60
            if minutes_since is not None and minutes_since < min_interval_minutes:
                logger.info(
                    f"PosterAgent: Last post was {minutes_since:.1f} minutes ago. "
                    f"Minimum interval is {min_interval_minutes} minutes. Skipping."
                )
                return []

            to_post = []

        posted_items = []

        for post in to_post:
            # hook/body ペア形式に対応。hook があれば POST1=hook、POST2=body をスレッド返信。
            # 旧形式（content のみ）はそのまま動作。
            hook = post.get("hook", "")
            body_text = post.get("body", "")
            if hook:
                content = hook
                existing_replies = post.get("thread_replies", [])
                thread_replies_override = ([body_text] if body_text else []) + existing_replies
            else:
                content = post.get("content", "")
                thread_replies_override = None
            post_type = post.get("post_type", "")
            has_affiliate = post.get("has_affiliate", False)
            affiliate_comment = post.get("affiliate_comment", "")

            # --- 競合防止: API呼び出し前に status を 'posting' へ先行書き込み ---
            # 複数プロセスが同時に起動した場合でも、ここで書き込んだ時点で
            # 他プロセスはこのアイテムを 'queued' として拾えなくなる。
            for q in queue:
                if q["id"] == post["id"]:
                    if q.get("status") != "queued":
                        # 別プロセスがすでに処理中または完了済み
                        logger.warning(
                            f"PosterAgent: [{post['id'][:8]}] status={q.get('status')} — "
                            "already being processed by another run. Skipping."
                        )
                        post = None
                        break
                    q["status"] = "posting"
                    q["posting_started_at"] = datetime.now().isoformat()
            self._save_queue(queue)

            if post is None:
                continue

            logger.info(
                f"PosterAgent: Posting [{post['id'][:8]}] "
                f"pattern={post.get('pattern')}, theme={post.get('theme')}"
            )

            media_urls = post.get("media_urls") or []
            main_media_url = media_urls[0] if media_urls else None

            # Post main content
            if has_credentials:
                main_post_id = self._post_text(content, media_url=main_media_url)
            else:
                main_post_id = self._mock_post(content, media_url=main_media_url)

            if not main_post_id:
                logger.error(f"PosterAgent: Failed to post [{post['id'][:8]}]. Skipping.")
                # Update status to failed in queue
                for q in queue:
                    if q["id"] == post["id"]:
                        q["status"] = "failed"
                        q["failed_at"] = datetime.now().isoformat()
                continue

            # Post thread_replies (スレッド分割続き) as sequential replies
            thread_reply_ids = []
            thread_replies = thread_replies_override if thread_replies_override is not None else post.get("thread_replies", [])
            prev_id = main_post_id
            for idx, reply_text in enumerate(thread_replies):
                time.sleep(3)
                if has_credentials:
                    r_id = self._post_text(reply_text, reply_to_id=prev_id)
                else:
                    r_id = self._mock_post(reply_text, reply_to_id=prev_id)
                if r_id:
                    thread_reply_ids.append(r_id)
                    prev_id = r_id
                    logger.info(f"PosterAgent: Thread reply [{idx+1}/{len(thread_replies)}] posted. ID: {r_id}")
                else:
                    logger.warning(f"PosterAgent: Failed to post thread reply [{idx+1}].")
                    break

            # Post affiliate comment as reply if applicable
            reply_id = None
            if has_affiliate and affiliate_comment:
                time.sleep(3)  # Small delay before reply
                if has_credentials:
                    reply_id = self._post_text(affiliate_comment, reply_to_id=main_post_id)
                else:
                    reply_id = self._mock_post(affiliate_comment, reply_to_id=main_post_id)

                if reply_id:
                    logger.info(f"PosterAgent: Affiliate comment posted as reply. ID: {reply_id}")
                else:
                    logger.warning(f"PosterAgent: Failed to post affiliate comment reply.")

            # Build history entry
            history_entry = {
                **post,
                "threads_post_id": main_post_id,
                "thread_reply_ids": thread_reply_ids,
                "affiliate_reply_id": reply_id,
                "posted_at": datetime.now().isoformat(),
                "status": "posted",
                "metrics": None,
                "metrics_fetched_at": None,
            }
            history.append(history_entry)

            # Update queue status
            for q in queue:
                if q["id"] == post["id"]:
                    q["status"] = "posted"
                    q["posted_at"] = datetime.now().isoformat()
                    q["threads_post_id"] = main_post_id

            posted_items.append(history_entry)
            logger.info(f"PosterAgent: Successfully posted [{post['id'][:8]}]. Threads ID: {main_post_id}")

        self._save_queue(queue)
        self._save_post_history(history)

        logger.info(f"PosterAgent: Posted {len(posted_items)} items.")
        return posted_items
