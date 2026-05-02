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
        # Try metrics first, then fall back to metrics_24h
        metrics = post.get("metrics") or post.get("metrics_24h")
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
        """Classify the first line style of a post.
        Updated 2026-04-12: Prioritize declaration/statement style (most effective pattern).
        """
        if not content:
            return "unknown"
        first_line = content.strip().split("\n")[0].strip()

        # 宣言・解説形式が最強（バズ実績から確認）
        # パターン: 「〇〇の自分が〜」「〇〇が失敗する理由」「〇〇をやってわかったこと」など
        if ("の自分が" in first_line or "が失敗" in first_line or
            "をやってわかった" in first_line or "をやって気づいた" in first_line or
            ("した" in first_line or "だった" in first_line) and len(first_line) <= 30):
            return "declaration_statement"  # ⭐ 最高の成績

        if first_line.endswith("？") or first_line.endswith("?"):
            return "question"
        elif first_line.startswith("【") or first_line.startswith("「"):
            return "bracket_open"
        elif any(char.isdigit() for char in first_line[:3]):
            return "number_lead"
        elif len(first_line) <= 20:
            return "short_punchy"
        elif "する方法" in first_line or "やり方" in first_line:
            return "how_to"
        else:
            return "statement"

    def _save_markdown_report(self, feedback):
        """Generate a human-readable markdown report for the user."""
        path = self.data_dir / "analysis-latest.md"
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        report = [
            f"# 📊 Threads運用分析レポート ({date_str})",
            "",
            "## 📈 全体概況",
            f"- **分析対象投稿数**: {feedback['total_posts_analyzed']}件",
            f"- **直近の傾向**: {feedback.get('note', '順調にデータを蓄積中。')}",
            "",
            "## 🏆 トップパフォーマンス（学ぶべき点）",
        ]
        
        if not feedback["top_performers"]:
            report.append("- データ不足のため、まだ特定できません。")
        else:
            for i, p in enumerate(feedback["top_performers"], 1):
                report.append(f"### {i}. スコア: {p['engagement_score']:.2f}")
                report.append(f"> {p['content_preview']}...")
                report.append(f"- **型**: `{p['pattern']}` / **テーマ**: `{p['theme']}`")
                report.append("")

        report.extend([
            "## ⚠️ 要改善（AI臭・反応が薄い原因）",
        ])
        
        if not feedback["bottom_performers"]:
            report.append("- データ不足のため、まだ特定できません。")
        else:
            for i, p in enumerate(feedback["bottom_performers"], 1):
                report.append(f"### 課題投稿 (スコア: {p['engagement_score']:.2f})")
                report.append(f"> {p['content_preview']}...")
                report.append("- **推測される原因**: 1行目のフックが弱い、または内容が「どこかで見たAI一般論」になっている可能性があります。")
                report.append("")

        report.extend([
            "## 🛠️ 次回への改善指示 (Writerへの指令)",
            "### ✅ 積極的に使うべき要素",
            f"- **好反応なタイトル型**: {', '.join(feedback['recommended_first_line_styles']) or 'データ収集中'}",
            f"- **鉄板パターン**: {', '.join(feedback['high_performing_patterns']) or 'データ収集中'}",
            "",
            "### ❌ 排除すべき要素",
            f"- **避けるべきテーマ**: {', '.join(feedback['avoid_themes']) or 'なし'}",
            f"- **避けるべきパターン**: {', '.join(feedback['avoid_patterns']) or 'なし'}",
            "",
            "---",
            "> [!TIP]",
            "> このレポートは `analyst` エージェントが実行されるたびに更新されます。",
            "> もしいいねが伸びない場合は、記事の『毒気（独自視点）』が足りないサインです。"
        ])
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        logger.info(f"AnalystAgent: Markdown report saved to {path.name}")

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

        # Filter to only posts that have metrics (use metrics_24h since metrics field may not exist)
        posts_with_metrics = [p for p in history if (p.get("metrics") or p.get("metrics_24h")) and p.get("status") == "posted"]

        if len(posts_with_metrics) < 1:
            logger.info("AnalystAgent: No posts with metrics found. Writing default feedback.")
            feedback = self._default_feedback()
            self._save_json(feedback_path, feedback)
            self._save_markdown_report(feedback)
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
            self._save_markdown_report(feedback)
            return feedback

        # Sort by engagement score
        scored_posts.sort(key=lambda x: x["engagement_score"], reverse=True)

        # --- Analysis logic (same as before, but with lower threshold for reports) ---
        # (Rest of analysis logic remains the same for internal JSON, but we always produce the MD)
        
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
        avoid_patterns = [p for p, avg in sorted_patterns if avg < 0.2] # Scarier threshold

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
        avoid_themes = [t for t, avg in sorted_themes if avg < 0.1]

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

        # --- Top / Bottom performers ---
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
            for p in scored_posts[-3:] if p not in scored_posts[:3] # Don't duplicate
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
            # 【2026-04-12更新】構造分析に基づくガイドライン
            "structure_guidelines": {
                "recommended_character_count": "150-250字（短めが勝ち。全体平均241字より32%短い投稿がいいね獲得率2倍以上）",
                "recommended_line_breaks": "8-10回（1改行あたり15-20字。スマートフォン視認性最優先）",
                "most_effective_opening_style": "declaration_statement（宣言・解説形式が11%のいいね獲得率を実現。他の形式は5%以下）",
                "top_performing_pattern": "story_hook（個人体験＋共感型。平均いいね4.0個がトップ）",
                "secondary_pattern": "number_hook（具体的な数字で訴求。ビュー最高1290）",
                "avoid_elements": [
                    "リスト形式の過剰使用（ボトム10は50%使用。伸びる投稿は30%）",
                    "疑問形での終わり（読者に判断委ねるより、筆者が結論を言い切る方が効果的）",
                    "平坦な長文（～です。～ます。の繰り返しは視認性と完読率が低下）"
                ],
                "content_structure": "導入（宣言フック1行）→ 本論（背景＋具体例 4-6行）→ 終わり（結論 1-2行）",
                "key_success_factors": [
                    "冒頭1行で世界観確立（「理学療法士の自分が…」など個人視点の前景化）",
                    "簡潔さ（トップ10の文字数168字。描写削除・体言止めで短くまとめる）",
                    "具体的な数字や年数を組み込む（「22年」「3ヶ月」など）",
                    "感情語・毒気を自然に織り込む（共感を生む）"
                ]
            }
        }

        self._save_json(feedback_path, feedback)
        self._save_markdown_report(feedback)
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
            "note": "分析対象の投稿データがまだ蓄積されていません。まずは投稿を続けましょう。",
        }
