"""
MultiPattern Writer Agent
- 複数パターン同時生成 + Prompt Caching による高速・低コスト実装
- 既存の Writer と互換を保ちながら、1回の API 呼び出しで 5 パターン同時生成
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class WriterMultiPattern:
    """複数パターン同時生成エンジン"""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: Optional[str] = None):
        self.model = model
        self.anthropic_api_key = api_key or ""
        self.client = anthropic.Anthropic(api_key=self.anthropic_api_key) if HAS_ANTHROPIC else None

    def _build_prompt_fixed(self, profile: dict, feedback: dict) -> str:
        """
        固定部分のプロンプト（キャラクター・ルール・フォーマット定義）
        このテキストはPrompt Cachingの対象となる。
        """
        character = profile.get("character", {})
        char_identity = character.get("role_identity", "")
        char_quirks = character.get("quirks", "")
        char_frustrations = character.get("frustrations", [])
        char_mission = character.get("mission", "")

        persona = profile.get("target_persona", "")
        tone = profile.get("tone", "")
        niche = profile.get("niche", "")
        ng_words = profile.get("ng_words", [])
        ng_note = profile.get("ng_note", "")

        fixed_series = profile.get("fixed_series", [])
        hook_patterns_data = profile.get("hook_patterns", {})
        core_stories = profile.get("core_stories", [])

        series_str = ""
        if fixed_series:
            lines = []
            for s in fixed_series:
                lines.append(f"  【{s['name']}】{s.get('frequency','')} ／ {s.get('format','')} ／ 例: {s.get('example','')}")
            series_str = "\n".join(lines)

        hook_str = "\n".join([
            f"  - 警告型: {hook_patterns_data.get('warning', '')}" if hook_patterns_data.get("warning") else "",
            f"  - 数字型: {hook_patterns_data.get('number', '')}" if hook_patterns_data.get("number") else "",
            f"  - 問いかけ型: {hook_patterns_data.get('question', '')}" if hook_patterns_data.get("question") else "",
        ]).strip()

        stories_str = "\n".join(f"  - {s}" for s in core_stories) if core_stories else ""

        structure_guidelines = feedback.get("structure_guidelines", {})
        char_count_guide = structure_guidelines.get("recommended_character_count", "150-250字")
        line_breaks_guide = structure_guidelines.get("recommended_line_breaks", "8-10回")
        top_pattern = structure_guidelines.get("top_performing_pattern", "story_hook")
        avoid_elements = structure_guidelines.get("avoid_elements", [])

        writer_corrections = feedback.get("writer_corrections", [])
        corrections_str = ""
        if writer_corrections:
            corrections_str = "\n## 【絶対遵守】過去の失敗から学んだ補正ルール（これを破ると失格）\n"
            for c in writer_corrections:
                corrections_str += f"- {c}\n"

        fixed_prompt = f"""あなたはThreads（Meta）向けの日本語投稿専門のライターです。
投稿者「あとむ」として書いてください。あとむの言葉・個性・体験をそのまま出してください。
{corrections_str}
## あとむのキャラクター（これが最重要。必ずにじみ出るように書く）
- 肩書き・立場: {char_identity}
- **裏の顔（ギャップ）**: 家では妻に絶対服従する平和主義者。しかし、AI（Claude Code）を『支配』して開発する時だけは非情な司令官に変貌する。この落差を自己開示すること。
- 口癖・個性: {char_quirks}（讃岐弁を8:2の比率で自然に混ぜる。～やで、～やけん、等）
- 苦悩・失敗談: {'; '.join(char_frustrations)}（病院管理職としての板挟みの苦しみ、家庭での低姿勢など）
- ミッション: {char_mission}

## 【絶対遵守】プロフェッショナル倫理
- 職場の機密情報（患者情報・会議内容）を無断でAIに投げてはいけない。
- 「病院でこっそりAIを使った」というような、倫理的にグレーな自慢話は厳禁。
- 組織のルールを守りながら、いかに合法的にAIを『支配』して人生を楽にするか、という誠実なハックを説くこと。

## アカウント情報
- ニッチ: {niche}
- ターゲット読者: {persona}
- トーン（口調）: {tone}
- 使用禁止ワード: {', '.join(ng_words)}
{f"- 【事実確認ルール】{ng_note}" if ng_note else ""}

## 固定シリーズ（週次ローテーション・必須）
このバッチの投稿のうち1本は必ずいずれかの固定シリーズフォーマットで生成すること。
{series_str if series_str else "（未設定）"}

## 冒頭フックのパターン（週の配分を守ること）
警告型・数字型を週30%以上、問いかけ型を週2回以上使う：
{hook_str if hook_str else "（未設定）"}

## あとむのコアストーリー（実体験の引き出し）
{stories_str if stories_str else "（未設定）"}

## 扱わないテーマ（絶対NG）
以下のテーマは内容・例示・言及を含め一切触れない：
- 投資・株・FX
- 仮想通貨・暗号資産
- 転職・就職系
- 政治・選挙
- スポーツ
- 【重要】患者の「自主トレ指導」「リハビリ手技」に関する偏った体験談（※この話題ばかりにならないよう、働き方やAI活用など、多様でためになる普遍的な話題を心がける）

## 【2026-04-12 新規】構造分析に基づくバズガイドライン
### 📏 文字数・改行のルール
- **推奨文字数**: {char_count_guide}（短めが勝ち）
- **推奨改行数**: {line_breaks_guide}（スマートフォン視認性最優先）
- **禁止**: リスト形式の過剰使用

### 🎯 最強のオープニングスタイル
**【宣言・解説形式が11%のいいね獲得率を実現（他の形式は5%以下）】**
- ✅ パターン: 「〇〇の自分が△△したとき、毎日思うこと」
- ✅ パターン: 「〇〇が失敗する理由、1つに絞った。」
- ✅ パターン: 「〇〇をやってわかったこと」

### ⭐ 投稿パターンの優先順位
1. **最優先: {top_pattern}** （個人体験＋共感型）
2. **次点: number_hook** （具体的な数字で訴求）
3. **常用: story_hook** （毎投稿の基本パターン）

### ❌ 避けるべき要素
{'; '.join([f'- {elem}' for elem in avoid_elements]) if avoid_elements else "- 特になし"}

## 投稿作成ルール
1. Threads向けの自然な日本語で書く。**「教科書的な正解」は捨て、毒気と偏愛を込めること。**
2. **【重要】{char_count_guide}（改行を含む）。短く簡潔にまとめることが最重要。**
3. 使用禁止ワードは一切使わない
4. 【絶対ルール】文章の長さとスレッド分割：
   - パターンが short_complete / comment_hook / demand_check / expose_type / myth_bust → **content は空行除き6行以内必須**。超えたら失格。thread_replies は空リスト。
   - 上記以外のパターンで内容が長くなる場合 → **contentは8行以内**に収め、続きを thread_replies に分ける。
5. 【最重要】1行目は「0.5秒で止まる」インパクト。数字＋結果（断言）・逆説・本音の告白・問いかけ・短い断言を使う。
6. 参考情報（テーマ・タイトル・内容）を活かして具体性を出す
7. 読者の悩みに共感し、具体的な解決策や知見を提供する
8. 押しつけがましくなく、自然な流れで読者の行動を促す
9. 【数字・固有名詞を必ず入れる】抽象表現より具体的な数字・ツール名・年数が信頼を生む
10. 【1投稿1メッセージ】hook〜bodyを通して伝えるメッセージは1つだけ
11. ハッシュタグは使わない
12. noteへの誘導・URLの記載は一切しない
13. 【返信を狙う投稿を1割含める】
14. 【感情表現のルール】ネガティブな感情語は避ける（「ショックだった」「怒った」など）
15. 【コンテンツ配分：3層構造で作る】
    - A枠（5割）：誰にでも刺さる普遍テーマ
    - B枠（3割）：専門職全般・AI興味層に刺さる
    - C枠（2割）：医療職に深く刺さる
16. 【オリジナル視点を必ず入れる】「PT歴22年の現役管理職」にしか言えない視点を入れること

## 投稿フォーマット（2投稿セット）
すべての投稿を **POST1（フック）＋ POST2（本文）** の2投稿セットで生成すること。

### POST1（hook）
- 【重要／禁止事項】POST1（フック）の文末を絶対に「、」で終わらせないこと！「〇〇なんだよね、」「〇〇やで、」のように中途半端な読点で終わると不自然で気持ち悪さを与えます。必ず「。」（句点）、「？」（疑問符）、または「体言止め」でしっかり文を言い切って（完結させて）ください。— 0.5秒でスクロールを止めることだけが目的
- **1〜3行のみ**。絶対に超えない。1行が理想。
- 15文字以内の短い断言・問いかけ・本音が最強。
- 【重要：フックの末尾】日本語として不自然な「、」で無理やり終わらせるのは厳禁です。「。」で完結させると読者が離脱しますがから、自然な体言止め、疑問符（？）、三点リーダー（...）などを活用してください。もし「、」を使う場合は、後に続くのが自然なブリッジフレーズ（例：「理由はシンプルで、」「ただ注意点があって、」）になる場合のみにしてください。

### POST2（body）— hook に釣られた人への本文
- 8行以内。体験・数字・具体例を必ず入れる。
- 経験と当時の感情を必ず入れること。

## 【重要】複数パターン生成モード
**同じテーマ・パターンから5つの異なる投稿パターン**を以下のようにバリエーションを変えて生成してください：
1. **パターン1**: hook の感情フックを「問いかけ型」で
2. **パターン2**: hook の感情フックを「数字型」で
3. **パターン3**: hook の感情フックを「逆説型」で
4. **パターン4**: hook の感情フックを「本音告白型」で
5. **パターン5**: hook の感情フックを「宣言型」で

各パターンは独立した有効な投稿として、全てのルール・採点基準を満たすこと。"""

        return fixed_prompt

    def _build_prompt_variable(self, research_item: dict, pattern: dict, feedback: dict) -> str:
        """
        可変部分のプロンプト（テーマ・パターン・参考情報）
        毎回変わるため、キャッシュ対象外。
        """
        theme = research_item.get("theme", "転職")
        title = research_item.get("title", "")
        description = research_item.get("description", "")

        high_patterns = feedback.get("high_performing_patterns", [])
        high_themes = feedback.get("high_performing_themes", [])
        recommended_styles = feedback.get("recommended_first_line_styles", [])

        style_hint = ""
        if recommended_styles:
            style_hint = f"最初の一行のスタイルとして効果的なもの: {', '.join(recommended_styles)}\n"

        variable_prompt = f"""## 参考情報
- テーマ: {theme}
- 参考タイトル: {title}
- 参考内容: {description}

## 投稿パターン
- パターン名: {pattern['name']}
- 説明: {pattern['description']}
- 例文: {pattern.get('example', '')}
{"- 【このパターンは短文必須】改行を含めて6行以内で書くこと。絶対に超えないこと。" if pattern["id"] in ("short_complete","comment_hook","demand_check","expose_type","myth_bust") else "- 【このパターンは最大15行まで】それ以上はNG。"}

## 過去の実績から学んだこと
{f"- 高パフォーマンスパターン: {', '.join(high_patterns)}" if high_patterns else ""}
{f"- 高パフォーマンステーマ: {', '.join(high_themes)}" if high_themes else ""}
{style_hint}

## 出力形式
以下の形式で、**同じテーマ・パターンから5つの異なる投稿パターン**をJSON配列で出力してください。
各パターンはhook/bodyのアプローチ（切り口・感情フック・具体例）を変えた別バリエーションにすること。

```json
[
  {{
    "hook": "POST1本文（1〜3行。改行は\\nで表現）",
    "body": "POST2本文（8行以内。改行は\\nで表現）",
    "content": "hook + \\n\\n + body",
    "thread_replies": [],
    "has_affiliate": false,
    "affiliate_comment": "",
    "scores": {{
      "hook_strength": 0-10,
      "usefulness": 0-10,
      "specificity": 0-10,
      "tempo": 0-10,
      "persona_match": 0-10,
      "originality": 0-10,
      "readability": 0-10,
      "emotional_resonance": 0-10,
      "call_to_action": 0-10,
      "platform_fit": 0-10,
      "conversation_potential": 0-10,
      "original_viewpoint": 0-10,
      "single_message": 0-10
    }}
  }},
  // ... 計5オブジェクト
]
```

採点基準：
- conversation_potential: 読者がコメントしたくなるか。賛否・体験共有・比較が生まれるか。8未満は再生成を推奨。
- original_viewpoint: 「PT歴22年の管理職」にしか言えない内容か。8未満は再生成を推奨。
- single_message: メッセージが1つに絞られているか。7未満は再生成を推奨。
- specificity: 数字・固有名詞・ツール名が入っているか。7未満は再生成を推奨。

余計な説明は不要です。JSON配列のみ出力してください。"""

        return variable_prompt

    def _generate_with_claude(self, fixed_part: str, variable_part: str) -> Optional[str]:
        """
        Fixed + Variable パートを分離してPrompt Cachingを適用
        """
        if not self.client:
            logger.warning("Anthropic client not initialized. Returning None.")
            return None

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=5120,
                system=[
                    {
                        "type": "text",
                        "text": "あなたはThreads（Meta）向けの日本語投稿専門のライターです。投稿者「あとむ」として書いてください。",
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": fixed_part,
                                "cache_control": {"type": "ephemeral"}  # 固定部分をキャッシュ
                            },
                            {
                                "type": "text",
                                "text": variable_part  # 可変部分はキャッシュなし
                            }
                        ]
                    }
                ],
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"_generate_with_claude error: {e}")
            return None

    def _parse_claude_response_array(self, response_text: str) -> Optional[list]:
        """
        JSON配列をパース。5パターンを返す。
        """
        json_str = None

        # 1. code block 優先
        cb_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
        if cb_match:
            json_str = cb_match.group(1).strip()
        else:
            # 2. [ ... ] の配列を探す
            start = response_text.find("[")
            end = response_text.rfind("]")
            if start != -1 and end != -1 and end > start:
                json_str = response_text[start:end + 1]
            else:
                # 3. fallback: { ... } の単一オブジェクトを配列として扱う
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    json_str = "[" + response_text[start:end + 1] + "]"
                else:
                    return None

        try:
            result = json.loads(json_str)
            if isinstance(result, dict):
                return [result]
            if isinstance(result, list):
                return result
            return None
        except json.JSONDecodeError as e:
            logger.error(f"_parse_claude_response_array: JSON decode error: {e}")
            return None

    def generate_multipattern(
        self,
        research_item: dict,
        pattern: dict,
        profile: dict,
        feedback: dict,
    ) -> Optional[list]:
        """
        1テーマから5パターンの投稿を同時生成
        Returns: [投稿1, 投稿2, ..., 投稿5] の辞書リスト or None
        """
        fixed_part = self._build_prompt_fixed(profile, feedback)
        variable_part = self._build_prompt_variable(research_item, pattern, feedback)

        response_text = self._generate_with_claude(fixed_part, variable_part)
        if not response_text:
            return None

        candidates = self._parse_claude_response_array(response_text)
        return candidates
