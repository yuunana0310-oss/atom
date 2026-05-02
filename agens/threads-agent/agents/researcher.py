"""
Researcher Agent
- Searches YouTube API for topics based on theme_tree
- Identifies which themes lack content in research_cache
- Extracts useful information and saves to research_cache.json
- Falls back to mock data if no YouTube API key
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


MOCK_DATA_TEMPLATES = {
    "A枠_ClaudeCodeで資料づくりに衝撃（最優先・積極投稿）": [
        {
            "title": "疾患のリハプログラムをAIに聞いたらエビデンスつきで出てきた",
            "description": "Claude Codeで疾患別のリハプログラムを作成。エビデンスベースの提案が数分で完成。医療職の効率化の実例。",
            "source": "mock",
            "keyword": "Claude Code 医療 資料作成",
            "url": "https://www.youtube.com/mock/001"
        },
        {
            "title": "自分で作ると何時間もかかる資料がAIなら数分で大枠が出てくる",
            "description": "PT22年目が使い方を変えた話。院内マニュアル、患者向け説明資料、退院計画書の作成時間が激変。",
            "source": "mock",
            "keyword": "AI 医療事務効率化",
            "url": "https://www.youtube.com/mock/002"
        },
        {
            "title": "Claude Codeで一番衝撃だったのはアプリ開発じゃなくて資料づくりだった",
            "description": "医療職が実務で使えるAI活用法。エンジニアの作業ではなく、医療専門職の書類業務が激変する理由。",
            "source": "mock",
            "keyword": "医療職 AI活用 現場",
            "url": "https://www.youtube.com/mock/003"
        }
    ],
    "A枠_非エンジニアがアプリを作った（最優先・最拡散）": [
        {
            "title": "コード1行も書けない人間がアプリを動かした日のこと",
            "description": "非エンジニアPTがClaude Codeでリハカルテアプリを自作。プログラミング知識ゼロからのスタート。",
            "source": "mock",
            "keyword": "Claude Code ノーコード アプリ開発",
            "url": "https://www.youtube.com/mock/004"
        },
        {
            "title": "Claude Codeで3日間格闘して気づいたこと",
            "description": "医療職が開発で詰まる場面。エラーとの向き合い方、AIへの指示の出し方。専門職だからこそできる開発アプローチ。",
            "source": "mock",
            "keyword": "AI開発 非エンジニア 医療",
            "url": "https://www.youtube.com/mock/005"
        },
        {
            "title": "非エンジニアがAI開発で詰まる場面と突破した方法",
            "description": "コードが読めなくてもアプリが完成する理由。AIに医療知識を教えながら開発を進めるテクニック。",
            "source": "mock",
            "keyword": "Claude Code 医療アプリ",
            "url": "https://www.youtube.com/mock/006"
        }
    ],
    "C枠_医療職×AI実務（医療職20万人に刺さる）": [
        {
            "title": "文書作業をAIで週何時間削れたか、具体的な数字",
            "description": "SOAP記録、退院計画書、紹介状の下書きを自動化。PT22年の現場で実測した時間削減効果。",
            "source": "mock",
            "keyword": "医療文書 AI自動化 効率化",
            "url": "https://www.youtube.com/mock/007"
        },
        {
            "title": "サマリー・退院計画書をAIで下書きする実際の方法",
            "description": "患者情報を入れずに下書きを作るプロンプトテクニック。医療職の秘密を守りながらAIを活用する。",
            "source": "mock",
            "keyword": "医療記録 プロンプト 事例",
            "url": "https://www.youtube.com/mock/008"
        },
        {
            "title": "医療職がAIを怖いと感じる理由と実際のところ",
            "description": "個人情報、医療安全、倫理的配慮。医療職が知るべきAI使用の線引き。国家資格者の責任を果たす使い方。",
            "source": "mock",
            "keyword": "医療 AI倫理 個人情報保護",
            "url": "https://www.youtube.com/mock/009"
        }
    ],
    "D枠_AI業務効率化（会社員・専門職全般に刺さる）": [
        {
            "title": "定型メール・返信文の下書きをAIに任せたら週〇時間戻った",
            "description": "医療現場の日々の報告書、返信文、通知。定型業務をAIで自動化するプロセス。",
            "source": "mock",
            "keyword": "医療現場 AI 事務業務",
            "url": "https://www.youtube.com/mock/010"
        },
        {
            "title": "議事録・要約・報告書の初稿をAIで5分で終わらせる方法",
            "description": "会議の音声をAIで文字起こし、要約。医療現場の会議や委員会の記録時間が激変。",
            "source": "mock",
            "keyword": "会議録音 AI文字起こし",
            "url": "https://www.youtube.com/mock/011"
        },
        {
            "title": "会議の文字起こし自動化、使ったツールと正直な感想",
            "description": "Claudeを使った実務。複数の音声ツールの比較と、医療現場での実用性。",
            "source": "mock",
            "keyword": "音声AI 医療現場 実用",
            "url": "https://www.youtube.com/mock/012"
        }
    ],
    "D枠_スマホでもできるAI（ターゲット読者への刺さりが強い）": [
        {
            "title": "スマホだけで使えるAIツール、正直に選んだ3つ",
            "description": "忙しい医療職向け。通勤中や休憩時間にできるAI活用法。PCがなくても始められる環境。",
            "source": "mock",
            "keyword": "スマホ AI Claude",
            "url": "https://www.youtube.com/mock/013"
        },
        {
            "title": "通勤中にClaude使い始めたら時間の使い方が変わった",
            "description": "医療職の多忙な日々の中での効率化。スマホアプリで記事執筆、企画、学習。",
            "source": "mock",
            "keyword": "スマホアプリ 副業 AI",
            "url": "https://www.youtube.com/mock/014"
        },
        {
            "title": "PCなしで副業・ライティングをAI化する手順",
            "description": "医療職が副業を始めるまでの最小限のツール構成。スマホだけで月収を作る方法。",
            "source": "mock",
            "keyword": "副業 スマホのみ AI",
            "url": "https://www.youtube.com/mock/015"
        }
    ],
    "B枠_専門職×AI×副業（専門職全般に刺さる）": [
        {
            "title": "資格持ちの専門職がAI副業を始めると有利な理由",
            "description": "医療職・介護職・士業の強み。専門知識×AIで差別化される市場。noteで記事を売るまでの道。",
            "source": "mock",
            "keyword": "専門職 AI副業 note",
            "url": "https://www.youtube.com/mock/016"
        },
        {
            "title": "専門職×AI発信で月収が変わるまでの手順",
            "description": "PT22年目が実際に始めた副業の流れ。Threadsでの発信、noteでの販売、月3万から。",
            "source": "mock",
            "keyword": "医療職 副業 発信",
            "url": "https://www.youtube.com/mock/017"
        },
        {
            "title": "AIで副業を始めて気づいた、専門職の強みと盲点",
            "description": "医療知識は強みだが、ビジネス思考は不足。AIと一緒に補う。診療報酬制度やEBM思考がなぜ副業に効く。",
            "source": "mock",
            "keyword": "医療職 ビジネス 副業",
            "url": "https://www.youtube.com/mock/018"
        }
    ],
    "E枠_noteガイドのティーザー投稿（週2〜3本・note購買につなげる）": [
        {
            "title": "退院サマリー自分で書くと1時間、AIに頼ったら10分で下書き完成",
            "description": "Claude Codeで医療文書作成を自動化。noteで販売中の「医療職向けClaude活用ガイド」の実例。",
            "source": "mock",
            "keyword": "医療文書 AI効率化",
            "url": "https://www.youtube.com/mock/019"
        },
        {
            "title": "患者向けの疾患説明文、専門用語を一般語に変換するプロンプト",
            "description": "患者説明に必要な資料作成。AIで医学用語を一般向けに翻訳する具体例。",
            "source": "mock",
            "keyword": "患者説明 資料作成 AI",
            "url": "https://www.youtube.com/mock/020"
        }
    ],
    "季節フック_4月（新年度・春）": [
        {
            "title": "新年度が始まって1週間、正直しんどいと思ってる人へ",
            "description": "4月の医療現場。新人受け入れ、異動の疲労。AI活用で乗り切る方法。",
            "source": "mock",
            "keyword": "新年度 医療現場",
            "url": "https://www.youtube.com/mock/021"
        },
        {
            "title": "4月から管理職になった人に22年目が伝えたいこと",
            "description": "管理職初心者向け。上下の板挟みの現実と、AIでカバーできる時間的ゆとり。",
            "source": "mock",
            "keyword": "管理職 新任 AI支援",
            "url": "https://www.youtube.com/mock/022"
        }
    ]
}


class ResearcherAgent:
    def __init__(self, config, knowledge_dir, data_dir):
        self.config = config
        self.knowledge_dir = Path(knowledge_dir)
        self.data_dir = Path(data_dir)
        self.youtube_api_key = getattr(config, "YOUTUBE_API_KEY", None)
        self.youtube_search_url = getattr(config, "YOUTUBE_SEARCH_URL", "https://www.googleapis.com/youtube/v3/search")

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

    def _load_theme_tree(self):
        path = self.knowledge_dir / "theme_tree.json"
        return self._load_json(path, {})

    def _load_research_cache(self):
        path = self.data_dir / "research_cache.json"
        return self._load_json(path, [])

    def _save_research_cache(self, cache):
        path = self.data_dir / "research_cache.json"
        self._save_json(path, cache)

    def _count_cache_by_theme(self, cache):
        """Count how many cached items exist per top-level theme."""
        counts = {}
        for item in cache:
            theme = item.get("theme", "unknown")
            counts[theme] = counts.get(theme, 0) + 1
        return counts

    def _search_youtube(self, keyword, max_results=5):
        """Search YouTube API and return list of video info dicts."""
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": max_results,
            "key": self.youtube_api_key,
            "relevanceLanguage": "ja",
        }
        try:
            resp = requests.get(self.youtube_search_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                results.append({
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:300],
                    "source": "youtube",
                    "keyword": keyword,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "channel": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                })
            return results
        except requests.RequestException as e:
            logger.error(f"YouTube API error for keyword '{keyword}': {e}")
            return []

    def _get_mock_data(self, theme):
        """Return mock data for a given theme."""
        return MOCK_DATA_TEMPLATES.get(theme, [])

    def run(self):
        """
        Main run method.
        Returns list of new research items added.
        """
        logger.info("ResearcherAgent: Starting run")

        theme_tree = self._load_theme_tree()
        cache = self._load_research_cache()
        cache_counts = self._count_cache_by_theme(cache)

        new_items = []
        using_mock = not bool(self.youtube_api_key)

        if using_mock:
            logger.warning("ResearcherAgent: No YouTube API key found. Using mock data.")

        for theme, subtopics in theme_tree.items():
            current_count = cache_counts.get(theme, 0)
            if current_count >= 3:
                logger.info(f"ResearcherAgent: Theme '{theme}' already has {current_count} items. Skipping.")
                continue

            needed = 3 - current_count
            logger.info(f"ResearcherAgent: Theme '{theme}' needs {needed} more items.")

            if using_mock:
                mock_items = self._get_mock_data(theme)
                if mock_items:
                    for mock_item in mock_items[:needed]:
                        item = {
                            "id": str(uuid.uuid4()),
                            "theme": theme,
                            **mock_item,
                            "added_at": datetime.now().isoformat(),
                        }
                        cache.append(item)
                        new_items.append(item)
                        logger.info(f"ResearcherAgent: Added mock item for theme '{theme}': {mock_item.get('title', '')}")
            else:
                keywords = subtopics if isinstance(subtopics, list) else subtopics.get("投稿候補", [])
                for keyword in keywords[:needed]:
                    yt_results = self._search_youtube(keyword, max_results=3)
                    for yt_item in yt_results[:needed]:
                        item = {
                            "id": str(uuid.uuid4()),
                            "theme": theme,
                            **yt_item,
                            "added_at": datetime.now().isoformat(),
                        }
                        cache.append(item)
                        new_items.append(item)
                        logger.info(f"ResearcherAgent: Added YouTube item for theme '{theme}': {yt_item.get('title', '')}")

        self._save_research_cache(cache)
        logger.info(f"ResearcherAgent: Run complete. Added {len(new_items)} new items.")
        return new_items
