"""
Reviewer Agent (5% Human Interface)
- Loads drafts.json and displays each post one by one
- Human chooses: [a]pprove / [s]kip / [e]dit first line / [q]uit
- Approved posts → moved to queue.json with status "queued"
- Skipped posts remain in drafts.json with status "skipped"
- Designed to be done in ~10 minutes/day
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ANSI colors (disabled on Windows if not supported)
_USE_COLOR = sys.stdout.isatty() and os.name != "nt" or os.environ.get("FORCE_COLOR")

def _c(text, code):
    if _USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text

def cyan(t):   return _c(t, "36")
def green(t):  return _c(t, "32")
def yellow(t): return _c(t, "33")
def red(t):    return _c(t, "31")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")


class ReviewerAgent:
    def __init__(self, config, data_dir):
        self.config = config
        self.data_dir = Path(data_dir)

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

    def _load_drafts(self):
        return self._load_json(self.data_dir / "drafts.json", [])

    def _save_drafts(self, drafts):
        self._save_json(self.data_dir / "drafts.json", drafts)

    def _load_queue(self):
        return self._load_json(self.data_dir / "queue.json", [])

    def _save_queue(self, queue):
        self._save_json(self.data_dir / "queue.json", queue)

    def _display_post(self, post, index, total):
        """Print a formatted post for review."""
        score = post.get("score", 0)
        score_color = green if score >= 8.0 else yellow if score >= 7.0 else red

        print("\n" + "=" * 60)
        print(bold(f"  [{index}/{total}]  スコア: {score_color(str(score))}  "
                   f"パターン: {cyan(post.get('pattern', '-'))}  "
                   f"テーマ: {post.get('theme', '-')}"))
        print("=" * 60)

        # Show content with line numbers
        lines = post.get("content", "").split("\n")
        for i, line in enumerate(lines, 1):
            prefix = bold(yellow(f"  1行目 → ")) if i == 1 else f"  {i}行目   "
            print(f"{prefix}{line}")

        if post.get("has_affiliate") and post.get("affiliate_comment"):
            print(dim(f"\n  [PR] {post['affiliate_comment']}"))

        # Score breakdown
        detail = post.get("scores_detail", {})
        if detail:
            low_scores = {k: v for k, v in detail.items() if v < 7.5}
            if low_scores:
                print(dim(f"\n  低スコア項目: " +
                           ", ".join(f"{k}={v}" for k, v in low_scores.items())))

        print()

    def _prompt_action(self):
        """Get user action. Returns one of: approve, skip, edit, quit."""
        while True:
            raw = input(bold("  [a]承認  [s]スキップ  [e]1行目編集  [q]終了 > ")).strip().lower()
            if raw in ("a", "approve", "ok", "y", "yes", ""):
                return "approve"
            if raw in ("s", "skip", "n", "no"):
                return "skip"
            if raw in ("e", "edit"):
                return "edit"
            if raw in ("q", "quit", "exit"):
                return "quit"
            print("  a / s / e / q で入力してください")

    def _edit_first_line(self, post):
        """Let user edit the first line of the post. Returns modified post."""
        content = post.get("content", "")
        lines = content.split("\n")
        print(f"\n  現在の1行目: {bold(lines[0])}")
        new_first_line = input("  新しい1行目 > ").strip()
        if new_first_line:
            lines[0] = new_first_line
            post = dict(post)
            post["content"] = "\n".join(lines)
            post["edited"] = True
            post["edited_at"] = datetime.now().isoformat()
            print(green("  ✓ 編集しました"))
        else:
            print(dim("  変更なし"))
        return post

    def run(self):
        """
        Interactive review session.
        Returns dict with counts: approved, skipped, edited, total_reviewed.
        """
        drafts = self._load_drafts()
        pending = [d for d in drafts if d.get("status") == "draft"]

        if not pending:
            print(green("\n下書きはありません。ライターを先に実行してください。"))
            print(dim("  python main.py --agent writer --mode review\n"))
            return {"approved": 0, "skipped": 0, "edited": 0, "total_reviewed": 0}

        print(bold(f"\n=== 下書きレビュー ({len(pending)}件) ==="))
        print(dim("  スコア7.0以上が通過済み。あなたが最終判断します。"))
        print(dim("  目安: 1件30〜60秒 → 全部で約10分\n"))

        queue = self._load_queue()
        approved = 0
        skipped_count = 0
        edited = 0

        for i, post in enumerate(pending, 1):
            self._display_post(post, i, len(pending))
            action = self._prompt_action()

            if action == "quit":
                print(yellow(f"\n  中断しました（承認: {approved}件, スキップ: {skipped_count}件）"))
                break

            # Find the post in drafts list and update its status
            draft_idx = next(
                (j for j, d in enumerate(drafts) if d.get("id") == post["id"]),
                None
            )

            if action == "edit":
                post = self._edit_first_line(post)
                edited += 1
                # Re-display and ask again
                self._display_post(post, i, len(pending))
                action = self._prompt_action()
                if action == "quit":
                    print(yellow(f"\n  中断しました（承認: {approved}件, スキップ: {skipped_count}件）"))
                    break

            if action == "approve":
                approved_post = dict(post)
                approved_post["status"] = "queued"
                approved_post["approved_at"] = datetime.now().isoformat()
                queue.append(approved_post)
                if draft_idx is not None:
                    drafts[draft_idx]["status"] = "approved"
                approved += 1
                print(green(f"  ✓ キューに追加しました ({approved}件目)"))
            else:
                if draft_idx is not None:
                    drafts[draft_idx]["status"] = "skipped"
                skipped_count += 1
                print(dim("  → スキップ"))

        self._save_drafts(drafts)
        self._save_queue(queue)

        print(bold(f"\n=== レビュー完了 ==="))
        print(f"  承認: {green(str(approved))}件  "
              f"スキップ: {dim(str(skipped_count))}件  "
              f"編集あり: {yellow(str(edited))}件")
        print(f"  キュー残数: {len([q for q in queue if q.get('status') == 'queued'])}件\n")

        return {
            "approved": approved,
            "skipped": skipped_count,
            "edited": edited,
            "total_reviewed": approved + skipped_count,
        }
