"""
ScorerAgent — 手動で書いた投稿文を採点するエージェント。

Usage (via main.py):
    python main.py --agent score
    python main.py --agent score --post "投稿テキスト"
"""
import io
import json
import logging
import sys
from pathlib import Path

# Windows での文字化け対策
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

SCORE_LABELS = {
    "hook_strength":         "フック強度",
    "usefulness":            "有益性",
    "specificity":           "具体性（数字・固有名詞）",
    "tempo":                 "テンポ・読みやすさ",
    "persona_match":         "ペルソナ一致度",
    "originality":           "独自性",
    "readability":           "視認性（改行・短さ）",
    "emotional_resonance":   "感情共鳴",
    "call_to_action":        "行動誘発",
    "platform_fit":          "Threads適合度",
    "conversation_potential":"返信・コメント誘発力",
    "original_viewpoint":    "PT22年管理職の独自視点",
    "single_message":        "1投稿1メッセージ度",
}

THRESHOLDS = {
    "conversation_potential": 8.0,
    "original_viewpoint":     8.0,
    "single_message":         7.0,
    "specificity":            7.0,
}

PASSING_AVG = 7.0


class ScorerAgent:
    def __init__(self, config, knowledge_dir, data_dir):
        self.config = config
        self.knowledge_dir = Path(knowledge_dir)
        self.data_dir = Path(data_dir)
        self.api_key = getattr(config, "ANTHROPIC_API_KEY", None)
        self.model = getattr(config, "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def _load_json(self, path, default):
        p = Path(path)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _build_prompt(self, post_text: str) -> str:
        profile = self._load_json(self.knowledge_dir / "account_profile.json", {})
        feedback = self._load_json(self.data_dir / "feedback_instructions.json", {})

        character = profile.get("character", {})
        char_identity = character.get("role_identity", "PT歴22年の現役管理職×AI実践者")

        writer_corrections = feedback.get("writer_corrections", [])
        corrections_str = ""
        if writer_corrections:
            corrections_str = "\n## 【採点に使う補正ルール（これを破ると低点）】\n"
            for c in writer_corrections:
                corrections_str += f"- {c}\n"

        return f"""あなたはThreads投稿の採点専門家です。
以下の投稿を13項目で採点してください。

## 投稿者「あとむ」のプロフィール
{char_identity}
{corrections_str}
## 採点する投稿
---
{post_text}
---

## 採点基準（各0〜10点）
- hook_strength: フック強度。0.5秒でスクロールを止められるか
- usefulness: 有益性。読者にとって得になるか
- specificity: 具体性。数字・固有名詞・ツール名が入っているか
- tempo: テンポ。短い行・体言止め・読みやすいリズムか
- persona_match: ターゲット（医療職AI活用層）に刺さるか
- originality: 独自性。誰でも言えることだけでないか
- readability: 視認性。スマホで読みやすいか
- emotional_resonance: 感情共鳴。共感・驚き・本音があるか
- call_to_action: 行動誘発。フォロー・コメント・保存を促すか
- platform_fit: Threads適合度。文体・長さがプラットフォームに合っているか
- conversation_potential: 返信誘発力。賛否や体験共有が生まれるか（8未満は要改善）
- original_viewpoint: PT22年管理職にしか言えない視点があるか（8未満は要改善）
- single_message: 伝えたいことが1つに絞られているか（7未満は要改善）

## 出力形式（JSONのみ・説明不要）
{{
  "scores": {{
    "hook_strength": 数値,
    "usefulness": 数値,
    "specificity": 数値,
    "tempo": 数値,
    "persona_match": 数値,
    "originality": 数値,
    "readability": 数値,
    "emotional_resonance": 数値,
    "call_to_action": 数値,
    "platform_fit": 数値,
    "conversation_potential": 数値,
    "original_viewpoint": 数値,
    "single_message": 数値
  }},
  "strengths": ["良い点を2〜3つ"],
  "improvements": ["改善点を2〜3つ（具体的に）"],
  "rewrite_suggestion": "改善版の冒頭1〜2行（hook部分のみ）"
}}"""

    def _print_result(self, result: dict):
        scores = result.get("scores", {})
        avg = round(sum(scores.values()) / len(scores), 2) if scores else 0
        passed = avg >= PASSING_AVG

        print("\n" + "=" * 52)
        print("【採点結果】")
        print("=" * 52)

        for key, label in SCORE_LABELS.items():
            score = scores.get(key, 0)
            bar = "#" * int(score) + "-" * (10 - int(score))
            threshold = THRESHOLDS.get(key)
            warn = " !!" if threshold and score < threshold else ""
            print(f"  {label:<26} [{bar}]  {score:.1f}{warn}")

        print("-" * 52)
        verdict = "[合格]" if passed else "[不合格 7.0未満]"
        print(f"  平均スコア: {avg:.2f} / 10.0   {verdict}")

        threshold_fails = [
            f"{SCORE_LABELS[k]}（{scores.get(k, 0):.1f} < {v}）"
            for k, v in THRESHOLDS.items()
            if scores.get(k, 0) < v
        ]
        if threshold_fails:
            print("\n  ⚠ 個別要件 未達:")
            for f in threshold_fails:
                print(f"    - {f}")

        strengths = result.get("strengths", [])
        if strengths:
            print("\n【良い点】")
            for s in strengths:
                print(f"  + {s}")

        improvements = result.get("improvements", [])
        if improvements:
            print("\n【改善点】")
            for i in improvements:
                print(f"  > {i}")

        suggestion = result.get("rewrite_suggestion", "")
        if suggestion:
            print("\n【hook 改善案】")
            print(f"  {suggestion}")

        print("=" * 52 + "\n")
        return avg, passed

    def run(self, post_text: str = None, print_output: bool = True) -> dict:
        try:
            import anthropic
        except ImportError:
            logger.error("ScorerAgent: anthropic package not installed.")
            return {}

        if not self.api_key:
            logger.error("ScorerAgent: ANTHROPIC_API_KEY not set.")
            return {}

        if not post_text:
            print("投稿文を貼り付けてください（終了は空行2回）:\n")
            lines = []
            try:
                while True:
                    line = input()
                    if line == "" and lines and lines[-1] == "":
                        break
                    lines.append(line)
            except EOFError:
                pass
            post_text = "\n".join(lines).strip()

        if not post_text:
            print("テキストが空です。")
            return {}

        if print_output:
            print("\n採点中...")

        prompt = self._build_prompt(post_text)
        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("ScorerAgent: Failed to parse response.")
            return {}

        result = json.loads(raw[start:end])
        scores = result.get("scores", {})
        avg = round(sum(scores.values()) / len(scores), 2) if scores else 0
        result["avg_score"] = avg
        result["passed"] = avg >= PASSING_AVG

        if print_output:
            self._print_result(result)

        return result
