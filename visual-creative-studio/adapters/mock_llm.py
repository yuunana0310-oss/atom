"""モック LLM - ルールベースで動作する疑似LLM"""
import re
from adapters.base_llm import BaseLLM


class MockLLM(BaseLLM):
    """外部API不要のモックLLM"""

    def analyze_intent(self, user_text: str, context: dict) -> dict:
        """意図解析（core/intent_parser.pyに委譲）"""
        from core.intent_parser import parse_intent
        return parse_intent(user_text, context)

    def generate_response(self, prompt: str, context: dict) -> str:
        """応答生成（conversation.pyが担当するのでここでは最小限）"""
        return prompt

    def extract_content_params(self, user_text: str, mode: str) -> dict:
        """コンテンツパラメータ抽出"""
        from core.intent_parser import parse_intent
        result = parse_intent(user_text, {"mode": mode})
        return result.get("detected_params", {})

    # ============================================================
    # 漫画スクリプト生成
    # ============================================================

    def generate_manga_script(self, theme: str, panel_count: int = 4) -> list:
        """4コマ漫画スクリプト生成（テンプレート）"""
        if panel_count == 4:
            return self._generate_4panel_script(theme)
        else:
            return self._generate_multipage_script(theme, panel_count)

    def _generate_4panel_script(self, theme: str) -> list:
        """4コマ漫画テンプレート"""
        is_ai = any(kw in theme for kw in ["AI", "ai", "Claude", "GPT", "プログラミング", "コード"])
        is_work = any(kw in theme for kw in ["仕事", "会社", "上司", "残業", "会議"])

        if is_ai:
            return [
                {
                    "index": 0, "role": "導入",
                    "summary": "AIを使い始めようとする主人公",
                    "dialogue": "よし、今日こそAIを使いこなすぞ！",
                    "scene_description": "デスクに向かってパソコンを開く",
                    "expression_note": "やる気満々"
                },
                {
                    "index": 1, "role": "展開",
                    "summary": "プロンプトに悩む",
                    "dialogue": "えーと...何て指示すればいいんだ...？",
                    "scene_description": "画面の前で固まる",
                    "expression_note": "困惑"
                },
                {
                    "index": 2, "role": "ため",
                    "summary": "2時間経過",
                    "dialogue": "「AIに聞く前に自分で調べる」を\nAIに聞いてしまった...",
                    "scene_description": "時計が2時間進んでいる",
                    "expression_note": "脱力"
                },
                {
                    "index": 3, "role": "オチ",
                    "summary": "結局手動で作業",
                    "dialogue": "...手でやった方が早かったかも",
                    "scene_description": "手書きでノートに書いている",
                    "expression_note": "遠い目"
                }
            ]
        elif is_work:
            return [
                {
                    "index": 0, "role": "導入",
                    "summary": "意気込む朝",
                    "dialogue": "今日は定時で帰るぞ！",
                    "scene_description": "朝のオフィスに出勤",
                    "expression_note": "やる気"
                },
                {
                    "index": 1, "role": "展開",
                    "summary": "急な依頼",
                    "dialogue": "ちょっとこれ今日中にお願いできる？",
                    "scene_description": "上司が書類を持ってくる",
                    "expression_note": "焦り"
                },
                {
                    "index": 2, "role": "ため",
                    "summary": "仕事が増える",
                    "dialogue": "あ、ついでにこれも...",
                    "scene_description": "机の上に書類が山積み",
                    "expression_note": "絶望"
                },
                {
                    "index": 3, "role": "オチ",
                    "summary": "結局残業",
                    "dialogue": "定時とは...",
                    "scene_description": "暗いオフィスで一人",
                    "expression_note": "虚無"
                }
            ]
        else:
            topic = theme[:15] if len(theme) > 15 else theme
            return [
                {
                    "index": 0, "role": "導入",
                    "summary": "テーマの導入",
                    "dialogue": f"今日は{topic}について！",
                    "scene_description": "主人公の登場",
                    "expression_note": "期待"
                },
                {
                    "index": 1, "role": "展開",
                    "summary": "話が展開する",
                    "dialogue": "なるほど、こうすればいいのか！",
                    "scene_description": "何かを発見するシーン",
                    "expression_note": "ひらめき"
                },
                {
                    "index": 2, "role": "ため",
                    "summary": "予想外の展開",
                    "dialogue": "えっ、そうだったの！？",
                    "scene_description": "驚きのリアクション",
                    "expression_note": "驚き"
                },
                {
                    "index": 3, "role": "オチ",
                    "summary": "落とし込み",
                    "dialogue": "結局それが一番大事だったか...",
                    "scene_description": "納得の表情",
                    "expression_note": "納得"
                }
            ]

    def _generate_multipage_script(self, theme: str, panel_count: int) -> list:
        """複数コマ漫画テンプレート"""
        topic = theme[:15] if len(theme) > 15 else theme
        templates = [
            {"role": "導入", "dialogue": f"{topic}の話をしよう", "scene": "主人公登場", "expression": "期待"},
            {"role": "展開", "dialogue": "最初はこうだったんだ", "scene": "回想シーン", "expression": "懐かしい"},
            {"role": "展開", "dialogue": "でもこれが転機になった", "scene": "転機の場面", "expression": "真剣"},
            {"role": "クライマックス", "dialogue": "ここで全てが変わった！", "scene": "決定的瞬間", "expression": "衝撃"},
            {"role": "オチ", "dialogue": "結局、大事なのはこれだった", "scene": "エンディング", "expression": "穏やか"},
            {"role": "エピローグ", "dialogue": "次はあなたの番です", "scene": "読者へのメッセージ", "expression": "微笑"},
        ]
        panels = []
        for i in range(min(panel_count, len(templates))):
            t = templates[i]
            panels.append({
                "index": i, "role": t["role"],
                "summary": f"シーン{i + 1}",
                "dialogue": t["dialogue"],
                "scene_description": t["scene"],
                "expression_note": t["expression"]
            })
        return panels

    # ============================================================
    # スライドコンテンツ生成
    # ============================================================

    def generate_slide_contents(self, title: str, goal: str,
                                page_count: int, style: str) -> list:
        """
        スライドコンテンツ生成

        Args:
            title: ユーザーが指定したタイトル
            goal: 制作の目的 / テーマ
            page_count: 枚数
            style: スタイル名
        """
        # タイトルとゴールからテーマを推定
        theme_text = f"{title} {goal}"
        is_ai = any(kw in theme_text for kw in ["AI", "ai", "Claude", "GPT", "人工知能"])
        is_marketing = any(kw in theme_text for kw in ["マーケティング", "SNS", "集客", "発信"])
        is_intro = any(kw in theme_text for kw in ["入門", "基本", "初心者", "始め", "使い方"])
        is_app = any(kw in theme_text for kw in ["アプリ", "ツール", "使い方", "操作"])

        if is_ai and is_intro:
            return self._slides_ai_intro(title, goal, page_count)
        elif is_ai:
            return self._slides_ai_general(title, goal, page_count)
        elif is_marketing:
            return self._slides_marketing(title, goal, page_count)
        elif is_app or is_intro:
            return self._slides_howto(title, goal, page_count)
        else:
            return self._slides_generic(title, goal, page_count)

    def _slides_ai_intro(self, title: str, goal: str, count: int) -> list:
        display_title = title or "AI活用の基本"
        templates = [
            {"title": display_title, "subtitle": "今日から始めるAI活用", "body": "AIを味方につけて\n仕事を効率化しよう", "icon": "🤖"},
            {"title": "Step 1: まず触ってみる", "subtitle": "完璧を求めない", "body": "最初は簡単な質問から\n始めればOK", "icon": "👆"},
            {"title": "Step 2: 指示を工夫する", "subtitle": "プロンプトの基本", "body": "具体的に伝える → 良い結果\n曖昧な指示 → 微妙な結果", "icon": "✍️"},
            {"title": "Step 3: 繰り返し改善", "subtitle": "一発で完璧は無理", "body": "何度もやり取りして\nベストに近づける", "icon": "🔄"},
            {"title": "Step 4: 得意分野を知る", "subtitle": "AIの向き不向き", "body": "文章作成 → 得意\n最新ニュース → 苦手", "icon": "📊"},
            {"title": "Step 5: 日常に組み込む", "subtitle": "習慣化が最強", "body": "毎日1つAIに任せてみる\nそれだけで世界が変わる", "icon": "🚀"},
            {"title": "まとめ", "subtitle": "AI活用は「慣れ」がすべて", "body": "今日から始めてみよう！", "icon": "✨"},
        ]
        return self._build_slides(templates, count)

    def _slides_ai_general(self, title: str, goal: str, count: int) -> list:
        display_title = title or "AI × あなたの仕事"
        templates = [
            {"title": display_title, "subtitle": "変わる働き方", "body": "AIは「代替」ではなく\n「拡張」ツール", "icon": "🤖"},
            {"title": "使える場面", "subtitle": "日常業務での活用", "body": "メール下書き・議事録\n企画書・リサーチ", "icon": "💼"},
            {"title": "注意点", "subtitle": "AIの限界を知る", "body": "最終判断は人間が行う\n事実確認は必ず行う", "icon": "⚠️"},
            {"title": "実践のコツ", "subtitle": "成果を出すポイント", "body": "小さく始めて\n徐々に範囲を広げる", "icon": "🎯"},
            {"title": "まとめ", "subtitle": "", "body": "AIは使った人から\n差がつく時代", "icon": "✨"},
        ]
        return self._build_slides(templates, count)

    def _slides_marketing(self, title: str, goal: str, count: int) -> list:
        display_title = title or "SNS発信の全体像"
        templates = [
            {"title": display_title, "subtitle": "戦略的に発信しよう", "body": "闇雲に投稿しても\n結果は出ない", "icon": "📱"},
            {"title": "誰に届ける？", "subtitle": "ターゲットを絞る", "body": "全員に向けた発信は\n誰にも届かない", "icon": "🎯"},
            {"title": "何を伝える？", "subtitle": "価値の言語化", "body": "あなたの経験 ＝\n誰かの「知りたい！」", "icon": "💡"},
            {"title": "どう届ける？", "subtitle": "プラットフォーム選び", "body": "文章ならnote\nビジュアルならInstagram", "icon": "📊"},
            {"title": "今日から始めよう", "subtitle": "", "body": "完璧じゃなくていい\nまず1投稿から", "icon": "🚀"},
        ]
        return self._build_slides(templates, count)

    def _slides_howto(self, title: str, goal: str, count: int) -> list:
        """使い方・ハウツー系"""
        display_title = title or goal[:20] or "使い方ガイド"
        # goalからトピック抽出
        topic = goal[:20] if goal else title[:20] if title else "このツール"
        templates = [
            {"title": display_title, "subtitle": "分かりやすく解説", "body": f"{topic}を\nステップ形式で紹介します", "icon": "📖"},
            {"title": "Step 1: 準備する", "subtitle": "まずは環境を整えよう", "body": "必要なものを揃えて\n設定を済ませよう", "icon": "🔧"},
            {"title": "Step 2: 基本操作", "subtitle": "まずはここから", "body": "基本的な操作を\n覚えましょう", "icon": "👆"},
            {"title": "Step 3: 応用テクニック", "subtitle": "もっと使いこなす", "body": "知っておくと便利な\nワザを紹介", "icon": "⚡"},
            {"title": "Step 4: よくある質問", "subtitle": "困ったときは", "body": "よくあるトラブルと\n解決方法", "icon": "❓"},
            {"title": "まとめ", "subtitle": "今日から実践！", "body": f"{topic}を\n使いこなそう！", "icon": "✨"},
        ]
        return self._build_slides(templates, count)

    def _slides_generic(self, title: str, goal: str, count: int) -> list:
        """汎用スライド生成（タイトル・ゴールを最大限反映）"""
        display_title = title or goal[:20] or "テーマ"
        topic = goal[:20] if goal else title[:20] if title else "このテーマ"

        templates = [
            {"title": display_title, "subtitle": "分かりやすく解説", "body": f"{topic}について\nポイントを紹介します", "icon": "📌"},
            {"title": "ポイント 1", "subtitle": "最も大切なこと", "body": f"{topic}で\nまず押さえるべき点", "icon": "1️⃣"},
            {"title": "ポイント 2", "subtitle": "実践のコツ", "body": "実際に取り組む際の\n具体的なコツ", "icon": "2️⃣"},
            {"title": "ポイント 3", "subtitle": "注意すべき点", "body": "失敗しないための\n注意ポイント", "icon": "3️⃣"},
            {"title": "ポイント 4", "subtitle": "応用編", "body": "さらに効果を高める\n応用テクニック", "icon": "4️⃣"},
            {"title": "まとめ", "subtitle": "", "body": "今日から実践してみよう！", "icon": "✨"},
        ]
        return self._build_slides(templates, count)

    def _build_slides(self, templates: list, count: int) -> list:
        """テンプレートからスライドリストを構築"""
        slides = []
        for i in range(min(count, len(templates))):
            t = templates[i]
            slides.append({
                "index": i,
                "title": t["title"],
                "subtitle": t.get("subtitle", ""),
                "body_text": t.get("body", ""),
                "icon": t.get("icon", ""),
                "layout": "center"
            })
        # countがテンプレートより多い場合、追加スライドを生成
        if count > len(templates):
            for i in range(len(templates), count):
                slides.append({
                    "index": i,
                    "title": f"補足 {i - len(templates) + 1}",
                    "subtitle": "",
                    "body_text": "追加情報はここに",
                    "icon": "📄",
                    "layout": "center"
                })
        return slides
