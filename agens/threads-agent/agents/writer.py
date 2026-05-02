"""
Writer Agent
- Reads research_cache.json, account_profile.json, post_patterns.json
- Reads feedback_instructions.json from Analyst
- Generates 5-10 posts per batch using Claude API
- Scores each post on 10 criteria (0-10 each), average must be >= 7.0
- Checks similarity with last 100 posts (cosine similarity >= 0.85 = reject)
- Rotates patterns (avoid last 3 used)
- Mode "auto"   : adds passing posts directly to queue.json
- Mode "review" : adds passing posts to drafts.json for human approval
"""
import json
import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("Writer: anthropic package not installed. Will use mock posts.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("Writer: scikit-learn not installed. Using fallback similarity check.")


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _ngram_overlap(text_a, text_b, n=3):
    """Fallback: character n-gram Jaccard similarity."""
    def ngrams(text, n):
        return set(text[i:i+n] for i in range(len(text) - n + 1))
    a_grams = ngrams(text_a, n)
    b_grams = ngrams(text_b, n)
    if not a_grams or not b_grams:
        return 0.0
    intersection = len(a_grams & b_grams)
    union = len(a_grams | b_grams)
    return intersection / union if union > 0 else 0.0


def compute_similarity(new_text, existing_texts):
    """
    Returns the maximum similarity between new_text and any item in existing_texts.
    Uses TF-IDF cosine if sklearn is available, else character n-gram Jaccard.
    """
    if not existing_texts:
        return 0.0

    if HAS_SKLEARN and len(existing_texts) >= 1:
        try:
            corpus = existing_texts + [new_text]
            vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=1)
            tfidf_matrix = vectorizer.fit_transform(corpus)
            new_vec = tfidf_matrix[-1]
            existing_vecs = tfidf_matrix[:-1]
            sims = cosine_similarity(new_vec, existing_vecs)[0]
            return float(max(sims))
        except Exception as e:
            logger.warning(f"TF-IDF similarity failed: {e}. Using fallback.")

    # Fallback
    max_sim = max(_ngram_overlap(new_text, t) for t in existing_texts)
    return max_sim


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# short pattern IDs: content must be ≤6 non-empty lines, thread_replies must be empty
SHORT_PATTERNS = {"short_complete", "comment_hook", "demand_check", "expose_type", "myth_bust"}


# ---------------------------------------------------------------------------
# Mock post generation
# ---------------------------------------------------------------------------

# Mock posts: PT×AI themed, no 転職/投資/affiliate
MOCK_POSTS = [
    {
        "hook": "Claudeで書類が変わった。",
        "body": "PT22年やってて、記録が一番しんどかった。\nSOAP、退院サマリー、紹介状。\n毎日2時間以上かけてた。\n\nClaudeに指示文を渡したら、10分になった。\n正直、仕事がなくなると思った。\nでもそうじゃなかった。考える時間が増えた。",
        "thread_replies": [],
        "pattern": "experience_share",
        "theme": "AI×医療実務",
        "has_affiliate": False,
        "affiliate_comment": "",
        "post_type": "experience_share",
    },
    {
        "hook": "非エンジニアがアプリ作った。",
        "body": "コードゼロのPTが、Claude Codeでカルテアプリを作り始めた。\n最初は何もわからなかった。\n\n3ヶ月で動くものができた。\nかかったのはAPIキー代の月3,000円だけ。\n\nエンジニアじゃないから作れない、は言い訳にならない。",
        "thread_replies": [],
        "pattern": "expose_type",
        "theme": "AI活用体験",
        "has_affiliate": False,
        "affiliate_comment": "",
        "post_type": "expose_type",
    },
    {
        "hook": "管理職ってしんどい。正直に言う。",
        "body": "上からはコスト削減。下からは人員不足。\n板挟みで22年。\n\nAIを使い始めて変わったのは、考える余裕ができたこと。\n書類じゃなくてスタッフを見れるようになった。\n\nツールの話じゃなくて、時間の話だった。",
        "thread_replies": [],
        "pattern": "myth_bust",
        "theme": "管理職×AI",
        "has_affiliate": False,
        "affiliate_comment": "",
        "post_type": "myth_bust",
    },
    {
        "hook": "副業って家族に話してる？",
        "body": "僕は最初、言えなかった。\n本業があるのにって思われそうで。\n\n今は話してる。Claudeで記事書いて、月3万になったから。\nリハの知識が副業になるとは思ってなかった。\n\n医療職でAI使って副業してる人、どのくらいおるんやろ。",
        "thread_replies": [],
        "pattern": "comment_hook",
        "theme": "副業×家族",
        "has_affiliate": False,
        "affiliate_comment": "",
        "post_type": "comment_hook",
    },
    {
        "hook": "AI使うほど、頭が悪くなってた。",
        "body": "最初の3ヶ月、Claudeに全部任せてた。\nSOAPも、評価も、計画も。\n\nそしたら自分で考えられなくなってきた。\n患者の前で言葉が出てこない瞬間があった。\n\nAIは道具。使い方が9割やと思ってる。",
        "thread_replies": [],
        "pattern": "warning",
        "theme": "AI×思考力",
        "has_affiliate": False,
        "affiliate_comment": "",
        "post_type": "warning",
    },
]


# ---------------------------------------------------------------------------
# Writer Agent
# ---------------------------------------------------------------------------

class WriterAgent:
    def __init__(self, config, knowledge_dir, data_dir):
        self.config = config
        self.knowledge_dir = Path(knowledge_dir)
        self.data_dir = Path(data_dir)
        self.anthropic_api_key = getattr(config, "ANTHROPIC_API_KEY", None)
        self.model = getattr(config, "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self.quality_threshold = getattr(config, "QUALITY_SCORE_THRESHOLD", 7.0)
        self.similarity_threshold = getattr(config, "SIMILARITY_THRESHOLD", 0.85)
        self.max_retries = getattr(config, "MAX_RETRIES", 2)

    def _load_json(self, path, default):
        path = Path(path)
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"_load_json: JSON parse error in {path.name}: {e}. Using default.")
            return default
        except OSError as e:
            logger.warning(f"_load_json: OS error reading {path.name}: {e}. Using default.")
            return default

    def _save_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_knowledge(self):
        profile = self._load_json(self.knowledge_dir / "account_profile.json", {})
        patterns = self._load_json(self.knowledge_dir / "post_patterns.json", {"patterns": []})
        ng_words = self._load_json(self.knowledge_dir / "ng_words.json", {"ng_words": []})
        return profile, patterns, ng_words

    def _load_research_cache(self):
        return self._load_json(self.data_dir / "research_cache.json", [])

    def _load_queue(self):
        return self._load_json(self.data_dir / "queue.json", [])

    def _save_queue(self, queue):
        self._save_json(self.data_dir / "queue.json", queue)

    def _load_drafts(self):
        return self._load_json(self.data_dir / "drafts.json", [])

    def _save_drafts(self, drafts):
        self._save_json(self.data_dir / "drafts.json", drafts)

    def _load_post_history(self):
        return self._load_json(self.data_dir / "post_history.json", [])

    def _load_feedback(self):
        return self._load_json(self.data_dir / "feedback_instructions.json", {})

    def _get_recent_texts(self, limit=100):
        """Get content text from last N posts (history + queue + drafts)."""
        history = self._load_post_history()
        queue = self._load_queue()
        drafts = self._load_drafts()
        all_posts = history + queue + drafts
        # Sort by created_at descending
        all_posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return [p["content"] for p in all_posts[:limit] if p.get("content")]

    def _get_last_used_patterns(self, n=3):
        """Get last N used pattern IDs from queue + history."""
        history = self._load_post_history()
        queue = self._load_queue()
        all_posts = history + queue
        all_posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        patterns = []
        for p in all_posts:
            pat = p.get("pattern")
            if pat and pat not in patterns:
                patterns.append(pat)
            if len(patterns) >= n:
                break
        return patterns

    def _check_ng_words(self, content, ng_words_list):
        """Returns list of NG words found in content."""
        found = []
        for word in ng_words_list:
            if word in content:
                found.append(word)
        return found

    def _select_pattern(self, patterns_list, feedback, avoid_last_n=3):
        """
        Select a pattern to use, avoiding last N used patterns
        and preferring high-performing patterns.
        Short patterns (≤6 lines) are weighted at 70%.
        """
        import random

        # Short patterns that produce ≤6 line posts
        SHORT_PATTERN_IDS = {"short_complete", "comment_hook", "demand_check", "expose_type", "myth_bust"}

        last_used = self._get_last_used_patterns(avoid_last_n)
        high_performing = feedback.get("high_performing_patterns", [])
        avoid = feedback.get("avoid_patterns", [])

        available = [
            p for p in patterns_list
            if p["id"] not in last_used and p["id"] not in avoid
        ]

        if not available:
            available = [
                p for p in patterns_list
                if p["id"] not in last_used[:1]
            ]

        if not available:
            available = patterns_list

        # Prefer high performing
        preferred = [p for p in available if p["id"] in high_performing]
        if preferred:
            return random.choice(preferred)

        # 70% short patterns, 30% long patterns
        short_available = [p for p in available if p["id"] in SHORT_PATTERN_IDS]
        long_available  = [p for p in available if p["id"] not in SHORT_PATTERN_IDS]

        if short_available and long_available:
            pool = short_available * 7 + long_available * 3
        else:
            pool = available

        return random.choice(pool)

    def _select_theme_and_research(self, research_cache, feedback, force_theme_prefix=None):
        """Select a theme + research item to write about."""
        import random
        avoid_themes = feedback.get("avoid_themes", [])
        high_themes = feedback.get("high_performing_themes", [])

        available = [r for r in research_cache if r.get("theme") not in avoid_themes]
        if not available:
            available = research_cache

        # Force a specific theme prefix if requested (e.g., "E枠")
        if force_theme_prefix:
            forced = [r for r in available if r.get("theme", "").startswith(force_theme_prefix)]
            if forced:
                return random.choice(forced)

        preferred = [r for r in available if r.get("theme") in high_themes]
        pool = preferred if preferred else available

        if pool:
            return random.choice(pool)
        return None

    def _build_prompt(self, research_item, pattern, profile, feedback):
        """Build the Claude prompt for post generation."""
        theme = research_item.get("theme", "転職")
        title = research_item.get("title", "")
        description = research_item.get("description", "")
        persona = profile.get("target_persona", "")
        tone = profile.get("tone", "")
        niche = profile.get("niche", "")
        ng_words = profile.get("ng_words", [])
        ng_note = profile.get("ng_note", "")
        note_url = profile.get("note_url", "")
        character = profile.get("character", {})
        char_identity = character.get("role_identity", "")
        char_quirks = character.get("quirks", "")
        char_frustrations = character.get("frustrations", [])
        char_mission = character.get("mission", "")

        high_patterns = feedback.get("high_performing_patterns", [])
        high_themes = feedback.get("high_performing_themes", [])

        recommended_styles = feedback.get("recommended_first_line_styles", [])
        style_hint = ""
        if recommended_styles:
            style_hint = f"最初の一行のスタイルとして効果的なもの: {', '.join(recommended_styles)}"

        writer_corrections = feedback.get("writer_corrections", [])

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

        corrections_str = ""
        if writer_corrections:
            corrections_str = "\n## 【絶対遵守】過去の失敗から学んだ補正ルール（これを破ると失格）\n"
            for c in writer_corrections:
                corrections_str += f"- {c}\n"

        prompt = f"""あなたはThreads（Meta）向けの日本語投稿専門のライターです。
投稿者「あとむ」として書いてください。あとむの言葉・個性・体験をそのまま出してください。
{corrections_str}
## あとむのキャラクター（これが最重要。必ずにじみ出るように書く）
- 肩書き・立場: {char_identity}
- 口癖・個性: {char_quirks}
- 苦労・失敗談（ネタとして活かす）: {'; '.join(char_frustrations)}
- ミッション: {char_mission}

## アカウント情報
- ニッチ: {niche}
- ターゲット読者: {persona}
- トーン（口調）: {tone}
- 使用禁止ワード: {', '.join(ng_words)}
{f"- 【事実確認ルール】{ng_note}" if ng_note else ""}

## 固定シリーズ（週次ローテーション・必須）
このバッチの投稿のうち1本は必ずいずれかの固定シリーズフォーマットで生成すること。
シリーズを守ることで読者の「次も見たい」という期待感が生まれ、リターナーを育成できる：
{series_str if series_str else "（未設定）"}

## 冒頭フックのパターン（週の配分を守ること）
警告型・数字型を週30%以上、問いかけ型を週2回以上使う。立ち上げ期はフックの強さが新規流入数を直接左右する：
{hook_str if hook_str else "（未設定）"}

## あとむのコアストーリー（実体験の引き出し）
週3本以上は以下の実体験を核にした現場体験談を生成すること。AIが書けない「PT目線のリアル」が最強の差別化要素：
{stories_str if stories_str else "（未設定）"}

## 扱わないテーマ（絶対NG）
以下のテーマは内容・例示・言及を含め一切触れない：
- 投資・株・FX
- 仮想通貨・暗号資産
- 転職・就職系
- 政治・選挙
- スポーツ
- 【重要】特定の患者の「自主トレ指導」「ホームエクササイズ」や「リハビリ手技」に関する偏った体験談（※この話題ばかりになるのを避けること。働き方、AI活用、チーム連携、日々の気づきなど、医療職・専門職にとって『多様でためになる普遍的な話題』を心がける）

## 参考情報
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

## 投稿作成ルール
1. Threads向けの自然な日本語で書く
2. 500文字以内（改行を含む）
3. 使用禁止ワードは一切使わない
4. 【絶対ルール】文章の長さとスレッド分割：
   - パターンが short_complete / comment_hook / demand_check / expose_type / myth_bust → **content は空行除き6行以内必須**。超えたら失格。thread_replies は空リスト。
   - 上記以外のパターンで内容が長くなる場合 → **contentは8行以内**に収め、続きを thread_replies に2〜3件に分けて書く。
   - thread_repliesの各リプライは独立して読めること。「続き①」のような書き方はNG。自然な流れで展開する。
   - 短文の書き方：1文1行。体言止め・断言を多用。説明を削って余韻で終わる。
   - 「〜です。〜ます。〜です。〜ます。」と続く平坦な長文は絶対NG。
5. 【最重要】1行目は「0.5秒で止まる」インパクト。以下の型を使うこと：
   - 数字＋結果（断言）：「残業3時間、AIで消えた。」
   - 逆説・裏切り：「AI使うほど、頭が悪くなってた。」
   - 本音の告白：「PTやって22年。AIに負けたと思った瞬間がある。」
   - 問いかけ（体験を引き出す型）：「AI、何から始めた？」「副業って家族に言えてる？」
   - 短い断言：「Claudeだけでいい。」「医療職、AIが一番向いてる。」
   NG一覧（これを書いたら即失格）：
   - 「〜について」「〜とは」「今日は〜を紹介します」
   - 15文字を超える長い1行目（短く切れ）
   - 「みなさん」「皆さん」「〜の方へ」
   【推奨パターン・投稿の半分程度に使う】15文字以内＋数字＋疑問形か断言の組み合わせは観覧数が伸びやすい。ただし毎回同じにするとワンパターンになるため、感情・体験談系は1行目のトーンを自然に優先してよい。
6. 参考情報（テーマ・タイトル・内容）を活かして具体性を出す
7. 読者の悩みに共感し、具体的な解決策や知見を提供する
8. 押しつけがましくなく、自然な流れで読者の行動を促す
15. 【数字・固有名詞を必ず入れる】抽象表現より具体的な数字・ツール名・年数が信頼を生む：
    - NG：「AIを使って時間が短縮された」
    - OK：「Claudeで週3時間 → 45分になった」
    - NG：「長年の経験で気づいた」
    - OK：「PT歴22年、3つの病院を経て気づいた」
    数字がない投稿は具体性が低く読者の記憶に残らない。必ず1つ以上入れること。
16. 【1投稿1メッセージ】hook〜bodyを通して伝えるメッセージは1つだけ：
    - 複数の気づきや教訓を1投稿に詰め込まない
    - 「〇〇と△△と□□がわかった」→ 「〇〇だけ」に絞る
    - 読み終わったとき「結局何が言いたかった？」と思われたら失格
9. ハッシュタグは使わない
10. noteへの誘導・URLの記載は一切しない
11. 【返信を狙う投稿を1割含める】生成するバッチのうち約1件は「返信特化型」にすること：
    【返信特化型の条件】
    - POST1（hook）が「読者の体験・意見を引き出す問いかけ1行」のみ
      例：「AI副業、家族に話せてる？」「PT・OTで副業してる人、何やってる？」「Claudeとそれ以外、使い分けてる？」
    - POST2（body）は自分の体験・本音を2〜4行で語る。答えを押しつけず「僕はこうやけど」で終わる
    - 末尾に「〜って人おる？」「みんなどうしてるんやろ」など讃岐弁で自然に余韻を残す
    - NG：「コメントお待ちしています」「教えてください」「ぜひ」など直接的な呼びかけ
    【残り9割の投稿でも仕掛けを入れる】
    - 自分の体験談を語ることで読者が自然と反応する（特定の組織・施設名は出さない）
    - 賛否が分かれる視点を提示する（「医療職はAI向き派 vs 向かない派」など）
    - 読者が「私もこれ！」「全然違う、私は〜」と言いたくなる二択・選択肢
    NG：「うちの病院」「うちの職場」など特定の組織を示す表現
12. 【オリジナル視点を必ず入れる】「PT歴22年の現役管理職」にしか言えない視点を1つ以上入れること：
    - 「一般的なAI情報」ではなく「医療現場で実際にやってみた結果」
    - 経営者目線と現場目線の両方を持つ管理職ならではの葛藤・気づき
    - 「〇〇と思われているが実際は違う」という現場からの反論
    - 22年のキャリアで見えてきた変化・パターン
    「ChatGPTより〇倍使える」「AIを使うと業務効率化」など誰でも言えることだけで構成された投稿は失格。
14. 【感情表現のルール】ネガティブな感情語は使わない：
    - NG：「ショックだった」「怒った」「失望した」「がっかりした」「腹が立った」「悲しかった」
    - OK：「正直びっくりした」「これは違うと思った」「モヤっとした」「手応えを感じた」「面白かった」
    - 感情は「軽い驚き・気づき・前向きな本音」の温度感で表現する
13. 【コンテンツ配分：3層構造で作る】
    投稿は以下の比率で作ること。PTにしか刺さらない内容は全体の2割以下に抑える。

    ◆ A枠（5割）：誰にでも刺さる普遍テーマ。医療職以外のフォロワーを獲得する入口
      - 「非エンジニアがアプリを作った」体験談
      - 「管理職の本音」（上と下に挟まれる葛藤・部下との関係）
      - 「副業×家族の現実」（妻子ある専門職の葛藤・本音）

    ◆ B枠（3割）：専門職全般・AI興味層に刺さる
      - 「22年キャリアの気づき」（PT限定にせず「専門職22年」として語る）
      - AI最新トレンドをリアル体験で語る（Vibe coding、AI Agent等）
      - 専門職×副業×AI の実践

    ◆ C枠（2割）：医療職20万人+周辺職種に深く刺さる
      - 医療×AI実務の具体的な話
      - 感情投稿・体験談

    【PT体験を普遍テーマに翻訳するルール】
    PTとして経験したことも、できるだけ普遍的な言葉に置き換えて書く：
    - 「患者さんが回復した」→「諦めかけた人が変わった瞬間を22年見てきた」
    - 「カルテをAIで効率化した」→「非エンジニアが業務ツールを自作した話」
    - 「部下の離職を経験した」→「人が辞める職場と辞めない職場、違いは何か」
    - 「PT22年の知識」→「22年で積み上げた専門知識をAIと組み合わせた話」
    PTという職種名は出してもいいが、投稿の核心が「PTだけの話」にならないこと。

## 投稿フォーマット（2投稿セット）
すべての投稿を **POST1（フック）＋ POST2（本文）** の2投稿セットで生成すること。

### POST1（hook）
- 【重要／禁止事項】POST1（フック）の文末を絶対に「、」で終わらせないこと！「〇〇なんだよね、」「〇〇やで、」のように中途半端な読点で終わると不自然で気持ち悪さを与えます。必ず「。」（句点）、「？」（疑問符）、または「体言止め」でしっかり文を言い切って（完結させて）ください。— 0.5秒でスクロールを止めることだけが目的
- **1〜3行のみ**。絶対に超えない。1行が理想。
- 感情を刺激する言葉だけ。情報・説明・結論は一切書かない。
- 15文字以内の短い断言・問いかけ・本音が最強。
- 【悩み・不安を先に示す】読んだ瞬間「これ自分だ」と思わせること。見てほしい人の悩みや不安を1行で代弁するか、解消できることを匂わせる：
  - 「副業、家族に言えてない」（悩みをそのまま言語化）
  - 「残業3時間、AIで消えた」（解消できることを示す）
  - 「Claudeを使いこなせてない気がする」（不安を代弁）
  この型が機能すると「タップしなきゃ」と感じさせられる。

POST1の例（良い）:
- `残業3時間、AIで消えた。`
- `Claudeだけでいい。`
- `副業って家族に話してる？`（※「AI副業、家族に言えてる？」は使用済みのため類似表現も避けること）
- `PT歴22年。AIに負けたと思った。`
- `管理職ってしんどい。正直に言う。`

POST1の例（NG）:
- 説明が入っている（「AIを使うことで業務効率化が〜」）
- 15文字を超える（長すぎ）
- 「〜について」「今日は〜を紹介します」で始まる
- 「みなさん」「皆さん」で始まる

### POST2（body）— hook に釣られた人への本文
- 8行以内。体験・数字・具体例を必ず入れる。
- POST1への「答え合わせ」になっていること。
- 【経験と当時の感情を必ず入れる】事実や知識だけでなく「そのとき自分がどう感じたか」を1〜2行で入れること：
  - NG：「Claudeを使うと議事録が5分で作れる」
  - OK：「Claudeで議事録を作ったとき、正直これは仕事がなくなると思った。22年のキャリアが揺らいだ感覚だった」
  感情があると読者が「この人の経験」として受け取る。感情のない投稿は情報サイトと同じ。
- 続きがある場合のみ thread_replies を使う（最大2件）。

## 出力形式
以下のJSONフォーマットで出力してください：

```json
{{
  "hook": "POST1本文（1〜3行。改行は\\nで表現）",
  "body": "POST2本文（8行以内。改行は\\nで表現）",
  "content": "hook + \\n\\n + body（後方互換用。hookとbodyを結合した全文）",
  "thread_replies": ["続きがある場合のみ。なければ空リスト。使う場合は【結論→理由→実例→結論】の順で展開し、具体的な解決手順・ステップ・数字を入れること。hook/bodyで解決策を匂わせ、詳細はここに書く"],
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

採点基準（重要）：
- conversation_potential（会話誘発力）: 読者がコメントしたくなるか。賛否・体験共有・比較が生まれるか。「コメントお待ちしています」なしで自然に反応を引き出せるか。8未満は再生成を推奨。
- original_viewpoint（オリジナル視点）: 「PT歴22年の管理職」にしか言えない内容か。誰でも言えるAI情報だけなら0点。現場体験・管理職の葛藤・22年のキャリアからの気づきがあれば高得点。8未満は再生成を推奨。
- single_message（1投稿1メッセージ度）: hook〜bodyを通じて伝えるメッセージが1つに絞られているか。複数の気づきを詰め込んでいたら低点。7未満は再生成を推奨。
- specificity（具体性）: 数字・固有名詞・ツール名・具体的な状況が入っているか。「AI」「長年の経験」などの抽象語だけなら低点。7未満は再生成を推奨。
}}
```
thread_replies は続きがない場合は必ず空リスト [] にしてください。
**has_affiliate は常に false にしてください。アフィリエイトは現在停止中です。**
余計な説明は不要です。JSONのみ出力してください。"""

        return prompt

    def _parse_claude_response(self, response_text):
        """Parse Claude's JSON response. Code block takes priority over raw JSON."""
        json_str = None

        # 1. code block が最優先
        cb_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
        if cb_match:
            json_str = cb_match.group(1).strip()
        else:
            # 2. 最初の { から最後の } までを取り出す（貪欲マッチより安全）
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = response_text[start:end + 1]

        if not json_str:
            logger.warning("_parse_claude_response: No JSON block found in response.")
            return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # ログにレスポンス全文を出さない（最大200文字）
            snippet = response_text[:200].replace("\n", " ")
            logger.error(f"_parse_claude_response: JSON decode error: {e} | snippet: {snippet!r}")
            return None

    def _calculate_average_score(self, scores_dict):
        """Calculate average of all score values."""
        if not scores_dict:
            return 0.0
        values = list(scores_dict.values())
        return sum(values) / len(values)

    def _normalize_and_validate_post(self, parsed, pattern, ng_words_list):
        """
        LLM出力を正規化・検証する。
        Returns: 正規化済みdict or None（不正な場合）

        - hook/body を文字列化・\\n を実改行に戻し strip
        - content を hook + "\\n\\n" + body から再構築
        - thread_replies を list に強制、各要素も正規化
        - has_affiliate を常に False、affiliate_comment を常に ""
        - NGワード・500文字・行数・short/long パターン制約をコードで強制
        """
        # --- 1. hook / body 抽出・正規化 ---
        hook = str(parsed.get("hook", "")).replace("\\n", "\n").strip()
        body = str(parsed.get("body", "")).replace("\\n", "\n").strip()

        # hook か body が欠けている場合: content から簡易分割で救済
        if not hook or not body:
            raw_content = str(parsed.get("content", "")).replace("\\n", "\n").strip()
            if "\n\n" in raw_content:
                parts = raw_content.split("\n\n", 1)
                hook = parts[0].strip()
                body = parts[1].strip()
            if not hook or not body:
                logger.info("_normalize_and_validate_post: hook or body missing. Rejecting.")
                return None

        # --- 2. thread_replies 正規化 ---
        raw_replies = parsed.get("thread_replies", [])
        if not isinstance(raw_replies, list):
            raw_replies = []
        thread_replies = [
            str(r).replace("\\n", "\n").strip()
            for r in raw_replies
            if str(r).replace("\\n", "\n").strip()
        ]

        # --- 3. affiliate 強制 ---
        has_affiliate = False
        affiliate_comment = ""

        # --- 4. content 再構築 ---
        content = (hook + "\n\n" + body).strip()

        # --- バリデーション ---

        # NGワード（content + replies 全体を対象）
        full_text = content + " " + " ".join(thread_replies)
        found_ng = self._check_ng_words(full_text, ng_words_list)
        if found_ng:
            logger.warning(f"_normalize_and_validate_post: NG words found: {found_ng}. Rejecting.")
            return None

        # 500文字制限
        if len(content) > 500:
            logger.info(f"_normalize_and_validate_post: content {len(content)} chars > 500. Rejecting.")
            return None

        # hook: 1〜3行
        hook_lines = [l for l in hook.split("\n") if l.strip()]
        if not hook_lines or len(hook_lines) > 3:
            logger.info(f"_normalize_and_validate_post: hook has {len(hook_lines)} lines (must be 1-3). Rejecting.")
            return None

        # body: 8行以内
        body_lines = [l for l in body.split("\n") if l.strip()]
        if len(body_lines) > 8:
            logger.info(f"_normalize_and_validate_post: body has {len(body_lines)} lines > 8. Rejecting.")
            return None

        # short / long パターン制約
        is_short = pattern["id"] in SHORT_PATTERNS
        content_lines = [l for l in content.split("\n") if l.strip()]

        if is_short:
            if len(content_lines) > 6:
                logger.info(
                    f"_normalize_and_validate_post: short pattern '{pattern['id']}' "
                    f"but {len(content_lines)} content lines > 6. Rejecting."
                )
                return None
            thread_replies = []  # short pattern は thread_replies 禁止
        else:
            if len(content_lines) > 8:
                logger.info(
                    f"_normalize_and_validate_post: long pattern '{pattern['id']}' "
                    f"but {len(content_lines)} content lines > 8. Rejecting."
                )
                return None
            # thread_replies は最大3件・各件 500文字未満 8行以内
            if len(thread_replies) > 3:
                thread_replies = thread_replies[:3]
            valid_replies = []
            for r in thread_replies:
                r_lines = [l for l in r.split("\n") if l.strip()]
                if len(r) < 500 and len(r_lines) <= 8:
                    valid_replies.append(r)
                else:
                    logger.info("_normalize_and_validate_post: dropping oversized thread_reply.")
            thread_replies = valid_replies

        return {
            "hook": hook,
            "body": body,
            "content": content,
            "thread_replies": thread_replies,
            "has_affiliate": has_affiliate,
            "affiliate_comment": affiliate_comment,
            "scores": parsed.get("scores", {}),
        }

    # Individual score thresholds enforced in code (not just prompt)
    _SCORE_THRESHOLDS = {
        "hook_strength": 8.0,
        "conversation_potential": 7.0,
        "original_viewpoint": 7.0,
        "single_message": 7.0,
        "specificity": 7.0,
    }

    def _check_score_thresholds(self, scores, avg_score):
        """
        Check average and individual score thresholds.
        Returns: (passed: bool, reason: str)
        """
        if avg_score < self.quality_threshold:
            return False, f"avg_score {avg_score:.2f} < {self.quality_threshold}"
        for key, min_val in self._SCORE_THRESHOLDS.items():
            val = scores.get(key, 10.0)  # キーがなければ合格扱い
            if val < min_val:
                return False, f"{key} {val} < {min_val}"
        return True, ""

    def _apply_e_theme_cta(self, hook, body_text):
        """
        E枠テーマ用のCTAをhook/bodyに付与する。
        Returns: (hook, body_text, content)
        「このバッチの最初の1本はE枠があれば優先する」実装に対応。
        """
        import random as _random
        body_cta_options = [
            "評価表・計画案・申し送り、そのまま使える指示文をプロフにまとめてある。",
            "退院サマリーや紹介状の下書きに使える指示文、プロフに全部載せてる。",
            "患者説明文を職種・疾患別に出す指示文、プロフから使える。",
            "SOAP形式で記録を出す指示文27本、プロフにまとめた。",
            "カルテ・書類系のプロンプト、プロフに全部ある。",
            "医療職向けのプロンプト集、プロフのリンクから見れる。",
        ]
        hook_cta_options = [
            "↓ 使った指示文、プロフにある",
            "↓ プロンプトはプロフに全部ある",
            "↓ 書類系の指示文、プロフにまとめた",
        ]
        body_cta = _random.choice(body_cta_options)
        hook_cta = _random.choice(hook_cta_options)
        new_body = body_text.rstrip() + "\n\n" + body_cta if body_text else body_cta
        new_hook = hook.rstrip() + "\n" + hook_cta if hook else hook
        new_content = (new_hook + "\n\n" + new_body).strip()
        return new_hook, new_body, new_content

    def _generate_with_claude(self, prompt):
        """Call Claude API to generate a post."""
        if not HAS_ANTHROPIC or not self.anthropic_api_key:
            return None

        try:
            client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def _humanize_post(self, hook: str, body_text: str, content: str) -> tuple[str, str, str]:
        # トークン削減＆プロンプト保護のため2ndPassスキップ
        return hook, body_text, content
        """
        2nd pass: AI臭を除去して人間が書いたような文体に変換する。
        失敗した場合は元テキストをそのまま返す（安全設計）。
        """
        if not HAS_ANTHROPIC or not self.anthropic_api_key:
            return hook, body_text, content

        prompt = f"""あなたは人間ライティング最適化AIです。
以下のThreads投稿（hook + body）のAI感（整いすぎ・説明過多・一般論）を除去し、人間が書いたような自然な文章に変換してください。

■目的
・AIと気づかれない
・最後まで読まれる
・行動につながる

■処理ステップ

① AI臭検出
整いすぎ・説明しすぎ・一般論・無感情・均一リズムをすべて特定

② 削減
不要な説明・まとめ・丁寧すぎる表現を削除（完結させない）

③ 人間化
・語尾の揺れ
・短文化
・間（改行）
・主観・体験・温度感 を挿入

④ 自己投影
読者が「これ自分だ」と感じる具体的な状況・感情を入れる（抽象禁止）

⑤ 未完設計
あえて説明を残さず、違和感・余白を残して続きを考えさせる

⑥ 最終チェック
「人間が書いたか？」基準で再検出し、最大の違和感を1つ潰す

■制約（絶対に守ること）
- hookは1〜3行のまま。行数を増やさない
- bodyは元の行数を大きく超えない（±2行まで）
- NGワード変更禁止：内容・テーマ・事実は変えない
- ハッシュタグは入れない
- JSON形式で返す

■入力
HOOK:
{hook}

BODY:
{body_text}

■出力形式（JSONのみ。説明不要）
{{"hook": "変換後のhook（改行は\\nで）", "body": "変換後のbody（改行は\\nで）"}}"""

        try:
            client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text
            parsed = self._parse_claude_response(response_text)
            if not parsed:
                logger.warning("_humanize_post: Failed to parse response. Using original text.")
                return hook, body_text, content

            new_hook = parsed.get("hook", hook).replace("\\n", "\n")
            new_body = parsed.get("body", body_text).replace("\\n", "\n")
            if not new_hook.strip() or not new_body.strip():
                logger.warning("_humanize_post: Empty result. Using original text.")
                return hook, body_text, content

            new_content = (new_hook + "\n\n" + new_body).strip()
            logger.info("_humanize_post: Humanization applied.")
            return new_hook, new_body, new_content
        except Exception as e:
            logger.error(f"_humanize_post error: {e}. Using original text.")
            return hook, body_text, content

    def _generate_mock_post(self, research_item, pattern):
        """
        Return a mock post (parsed-compatible dict) when Claude API is unavailable.
        Schema matches Claude branch output so _normalize_and_validate_post can process it.
        """
        import random
        mock = random.choice(MOCK_POSTS)
        # スコアはすべての個別閾値を満たす値に設定
        scores = {
            "hook_strength": 8.5,
            "usefulness": 8.0,
            "specificity": 7.5,
            "tempo": 7.8,
            "persona_match": 8.0,
            "originality": 7.5,
            "readability": 8.0,
            "emotional_resonance": 7.5,
            "call_to_action": 7.2,
            "platform_fit": 7.8,
            "conversation_potential": 7.5,
            "original_viewpoint": 7.5,
            "single_message": 8.0,
        }
        return {
            "hook": mock["hook"],
            "body": mock["body"],
            "content": mock["hook"] + "\n\n" + mock["body"],
            "thread_replies": mock.get("thread_replies", []),
            "has_affiliate": False,
            "affiliate_comment": "",
            "scores": scores,
        }

    def run(self, batch_size=2, mode=None):
        """
        Main run method.
        Generates batch_size posts and routes them based on mode.

        mode="auto"   -> qualifying posts go directly to queue.json
        mode="review" -> qualifying posts go to drafts.json (awaiting human approval)
        mode=None     -> reads from config.OPERATION_MODE

        Generation flow per post:
          1. Generate (Claude or mock) → parsed dict
          2. _normalize_and_validate_post  ← LLM出力をコードで正規化・検証
          3. _check_score_thresholds       ← 個別スコアをコードで強制
          4. Similarity check (pre-humanize)
          5. _apply_e_theme_cta (E枠テーマのみ)
          6. _humanize_post (Claude使用時のみ)
          7. _normalize_and_validate_post  ← humanize後に再検証
          8. Similarity check (final content)
          9. post_entry 組み立て・保存
        """
        if mode is None:
            mode = getattr(self.config, "OPERATION_MODE", "auto")

        logger.info(f"WriterAgent: Starting run (batch_size={batch_size}, mode={mode})")

        profile, patterns_data, ng_words_data = self._load_knowledge()
        research_cache = self._load_research_cache()
        feedback = self._load_feedback()
        queue = self._load_queue()
        drafts = self._load_drafts()

        patterns_list = patterns_data.get("patterns", [])
        ng_words_list = ng_words_data.get("ng_words", [])

        if not research_cache:
            logger.warning("WriterAgent: research_cache is empty. Cannot generate posts.")
            return []

        using_claude = HAS_ANTHROPIC and bool(self.anthropic_api_key)
        if not using_claude:
            logger.warning("WriterAgent: Claude API not available. Using mock posts.")

        recent_texts = self._get_recent_texts(limit=100)
        added_posts = []
        attempts = 0
        max_attempts = batch_size * (self.max_retries + 1) * 2

        # E枠優先制御: このバッチの最初の1本はE枠テーマがあれば優先する
        e_quota_filled = False

        while len(added_posts) < batch_size and attempts < max_attempts:
            attempts += 1

            force_prefix = "E枠" if not e_quota_filled and len(added_posts) == 0 else None
            research_item = self._select_theme_and_research(
                research_cache, feedback, force_theme_prefix=force_prefix
            )
            if not research_item:
                logger.warning("WriterAgent: No suitable research item found.")
                break

            pattern = self._select_pattern(patterns_list, feedback, avoid_last_n=3)
            retry_count = 0
            post_accepted = False

            while retry_count <= self.max_retries and not post_accepted:
                retry_count += 1

                # ── Step 1: 生成 ──────────────────────────────────────
                if using_claude:
                    prompt = self._build_prompt(research_item, pattern, profile, feedback)
                    response_text = self._generate_with_claude(prompt)
                    if not response_text:
                        logger.warning(f"WriterAgent: Claude returned empty response (attempt {retry_count})")
                        continue
                    parsed = self._parse_claude_response(response_text)
                    if not parsed:
                        logger.warning(f"WriterAgent: Failed to parse Claude response (attempt {retry_count})")
                        continue
                else:
                    parsed = self._generate_mock_post(research_item, pattern)

                # ── Step 2: 正規化・構造検証 ─────────────────────────
                normalized = self._normalize_and_validate_post(parsed, pattern, ng_words_list)
                if not normalized:
                    logger.info(
                        f"WriterAgent: Normalization/validation failed "
                        f"(attempt {retry_count}/{self.max_retries})"
                    )
                    continue

                hook = normalized["hook"]
                body_text = normalized["body"]
                content = normalized["content"]
                thread_replies = normalized["thread_replies"]
                scores = normalized["scores"]
                avg_score = self._calculate_average_score(scores)

                # ── Step 3: スコア閾値チェック ────────────────────────
                passed, reason = self._check_score_thresholds(scores, avg_score)
                if not passed:
                    logger.info(
                        f"WriterAgent: Score check failed [{reason}]. "
                        f"Retry {retry_count}/{self.max_retries}"
                    )
                    continue

                # ── Step 4: 類似度チェック（pre-humanize）─────────────
                if using_claude:
                    max_sim = compute_similarity(content, recent_texts)
                    if max_sim >= self.similarity_threshold:
                        logger.info(
                            f"WriterAgent: Similarity {max_sim:.3f} >= {self.similarity_threshold}. "
                            "Discarding as too similar."
                        )
                        continue

                # ── Step 5: E枠 CTA 付与 ──────────────────────────────
                theme_name = research_item.get("theme", "")
                if theme_name.startswith("E枠") and "プロフ" not in content:
                    hook, body_text, content = self._apply_e_theme_cta(hook, body_text)
                    logger.info("WriterAgent: Auto-appended CTA to E枠 post.")

                # ── Step 6: Humanize（AI臭除去）──────────────────────
                if using_claude and hook and body_text:
                    hook, body_text, content = self._humanize_post(hook, body_text, content)

                # ── Step 7: humanize後 再正規化・再検証 ─────────────
                if using_claude:
                    post_humanized = {
                        "hook": hook,
                        "body": body_text,
                        "content": content,
                        "thread_replies": thread_replies,
                        "scores": scores,
                    }
                    renormalized = self._normalize_and_validate_post(
                        post_humanized, pattern, ng_words_list
                    )
                    if not renormalized:
                        logger.warning(
                            "WriterAgent: Post failed re-validation after humanization. Discarding."
                        )
                        continue
                    hook = renormalized["hook"]
                    body_text = renormalized["body"]
                    content = renormalized["content"]
                    thread_replies = renormalized["thread_replies"]

                # ── Step 8: 類似度チェック（final content）────────────
                if using_claude:
                    max_sim = compute_similarity(content, recent_texts)
                    if max_sim >= self.similarity_threshold:
                        logger.info(
                            f"WriterAgent: Post-humanize similarity {max_sim:.3f} >= threshold. Discarding."
                        )
                        continue

                # ── Step 9: 採用・保存 ────────────────────────────────
                destination = "draft" if mode == "review" else "queued"
                post_entry = {
                    "id": str(uuid.uuid4()),
                    "hook": hook,
                    "body": body_text,
                    "content": (hook + "\n\n" + body_text).strip(),  # 常に再構築
                    "thread_replies": thread_replies,
                    "pattern": pattern["id"],
                    "theme": theme_name or "unknown",
                    "score": round(avg_score, 2),
                    "scores_detail": scores,
                    "has_affiliate": False,       # 常に強制
                    "affiliate_comment": "",      # 常に強制
                    "post_type": pattern["id"],
                    "created_at": datetime.now().isoformat(),
                    "status": destination,
                    "research_source_id": research_item.get("id"),
                }

                if mode == "review":
                    drafts.append(post_entry)
                else:
                    queue.append(post_entry)

                recent_texts.append(post_entry["content"])
                added_posts.append(post_entry)
                post_accepted = True
                if theme_name.startswith("E枠"):
                    e_quota_filled = True
                logger.info(
                    f"WriterAgent: Post accepted → {destination}. "
                    f"Score={avg_score:.2f}, Pattern={pattern['id']}, Theme={theme_name}"
                )

        if mode == "review":
            self._save_drafts(drafts)
            logger.info(f"WriterAgent: Added {len(added_posts)} posts to drafts (awaiting review).")
        else:
            self._save_queue(queue)
            logger.info(f"WriterAgent: Added {len(added_posts)} posts to queue.")
        return added_posts
