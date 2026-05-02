"""
Analyst Agent
- Reads post_history.json (posts with metrics)
- Calculates performance by pattern type, theme, first-line style
- Identifies top performers and underperformers
- Writes feedback_instructions.json for Writer
"""
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AnalystAgent:
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

    def _calculate_engagement_score(self, post):
        """Calculate an engagement score from metrics. Higher = better."""
        metrics = post.get("metrics", {})
        if not metrics:
            return None
        views = metrics.get("views", 0) or 0
        likes = metrics.get("likes", 0) or 0
        replies = metrics.get("replies", 0) or 0
        reposts = metrics.get("reposts", 0) or 0
        quotes = metrics.get("quotes", 0) or 0

        if views == 0:
            return 0.0

        # Engagement rate: weighted interactions / views
        score = (likes * 3 + replies * 5 + reposts * 4 + quotes * 4) / max(views, 1) * 100
        return round(score, 4)

    def _get_first_line_style(self, content):
        """Classify the first line style of a post."""
        if not content:
            return "unknown"
        first_line = content.strip().split("\n")[0].strip()

        if first_line.endswith("？") or first_line.endswith("?"):
            return "question"
        elif first_line.startswith("【") or first_line.startswith("「"):
            return "bracket_open"
        elif any(char.isdigit() for char in first_line[:3]):
            return "number_lead"
        elif len(first_line) <= 20:
            return "short_punchy"
        elif "した" in first_line or "だった" in first_line:
            return "past_experience"
        elif "する方法" in first_line or "やり方" in first_line:
            return "how_to"
        else:
            return "statement"

    def run(self):
        """
        Main run method.
        Analyzes post history and writes feedback_instructions.json.
        Returns the feedback dict.
        """
        logger.info("AnalystAgent: Starting run")

        post_history_path = self.data_dir / "post_history.json"
        feedback_path = self.data_dir / "feedback_instructions.json"

        history = self._load_json(post_history_path, [])

        # Filter to only posts that have metrics
        posts_with_metrics = [p for p in history if p.get("metrics") and p.get("status") == "posted"]

        if len(posts_with_metrics) < 3:
            logger.info(
                f"AnalystAgent: Only {len(posts_with_metrics)} posts with metrics. "
                "Need at least 3 for meaningful analysis. Writing default feedback."
            )
            feedback = self._default_feedback()
            self._save_json(feedback_path, feedback)
            return feedback

        # Compute engagement scores
        scored_posts = []
        for post in posts_with_metrics:
            score = self._calculate_engagement_score(post)
            if score is not None:
                scored_posts.append({**post, "engagement_score": score})

        if not scored_posts:
            feedback = self._default_feedback()
            self._save_json(feedback_path, feedback)
            return feedback

        # Sort by engagement score
        scored_posts.sort(key=lambda x: x["engagement_score"], reverse=True)

        # --- Pattern analysis ---
        pattern_scores = defaultdict(list)
        for post in scored_posts:
            pattern = post.get("pattern", "unknown")
            pattern_scores[pattern].append(post["engagement_score"])

        pattern_avg = {
            pattern: round(sum(scores) / len(scores), 4)
            for pattern, scores in pattern_scores.items()
        }
        sorted_patterns = sorted(pattern_avg.items(), key=lambda x: x[1], reverse=True)
        high_performing_patterns = [p for p, _ in sorted_patterns[:3]]
        avoid_patterns = [p for p, avg in sorted_patterns if avg < 0.5]

        # --- Theme analysis ---
        theme_scores = defaultdict(list)
        for post in scored_posts:
            theme = post.get("theme", "unknown")
            theme_scores[theme].append(post["engagement_score"])

        theme_avg = {
            theme: round(sum(scores) / len(scores), 4)
            for theme, scores in theme_scores.items()
        }
        sorted_themes = sorted(theme_avg.items(), key=lambda x: x[1], reverse=True)
        high_performing_themes = [t for t, _ in sorted_themes[:3]]
        avoid_themes = [t for t, avg in sorted_themes if avg < 0.3]

        # --- First line style analysis ---
        style_scores = defaultdict(list)
        for post in scored_posts:
            style = self._get_first_line_style(post.get("content", ""))
            style_scores[style].append(post["engagement_score"])

        style_avg = {
            style: round(sum(scores) / len(scores), 4)
            for style, scores in style_scores.items()
        }
        sorted_styles = sorted(style_avg.items(), key=lambda x: x[1], reverse=True)
        recommended_first_line_styles = [s for s, _ in sorted_styles[:3]]

        # --- Top / Bottom performers for reference ---
        top_posts = [
            {
                "id": p.get("id"),
                "content_preview": p.get("content", "")[:100],
                "pattern": p.get("pattern"),
                "theme": p.get("theme"),
                "engagement_score": p.get("engagement_score"),
            }
            for p in scored_posts[:3]
        ]
        bottom_posts = [
            {
                "id": p.get("id"),
                "content_preview": p.get("content", "")[:100],
                "pattern": p.get("pattern"),
                "theme": p.get("theme"),
                "engagement_score": p.get("engagement_score"),
            }
            for p in scored_posts[-3:]
        ]

        feedback = {
            "high_performing_patterns": high_performing_patterns,
            "avoid_patterns": avoid_patterns,
            "high_performing_themes": high_performing_themes,
            "avoid_themes": avoid_themes,
            "recommended_first_line_styles": recommended_first_line_styles,
            "pattern_avg_scores": pattern_avg,
            "theme_avg_scores": theme_avg,
            "top_performers": top_posts,
            "bottom_performers": bottom_posts,
            "total_posts_analyzed": len(scored_posts),
            "analysis_date": datetime.now().isoformat(),
        }

        self._save_json(feedback_path, feedback)
        logger.info(
            f"AnalystAgent: Analysis complete. "
            f"High patterns: {high_performing_patterns}. "
            f"High themes: {high_performing_themes}."
        )
        return feedback

    def _default_feedback(self):
        return {
            "high_performing_patterns": [],
            "avoid_patterns": [],
            "high_performing_themes": [],
            "avoid_themes": [],
            "recommended_first_line_styles": [],
            "pattern_avg_scores": {},
            "theme_avg_scores": {},
            "top_performers": [],
            "bottom_performers": [],
            "total_posts_analyzed": 0,
            "analysis_date": datetime.now().isoformat(),
            "note": "Insufficient data for analysis.",
        }
