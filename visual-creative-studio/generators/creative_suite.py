"""世界観統一セット生成"""
from generators.base_generator import BaseGenerator
from generators.design_generator import DesignGenerator
from core.state_schema import SessionState, SIZE_PRESETS
from adapters.mock_llm import MockLLM


class CreativeSuiteGenerator(BaseGenerator):
    """複数成果物を世界観統一で一括生成"""

    def __init__(self):
        self.design_gen = DesignGenerator()
        self.llm = MockLLM()

    def generate(self, state: SessionState) -> list:
        """世界観統一セットを生成"""
        results = []

        # クリエイティブスイートの構成を決定
        if not state.creative_suite:
            state.creative_suite = [
                {"item_type": "youtube_thumbnail", "title": "YouTubeサムネイル", "size": "youtube_thumbnail"},
                {"item_type": "instagram_carousel", "title": "Instagramカルーセル", "size": "instagram_portrait", "count": 5},
                {"item_type": "service_intro", "title": "サービス紹介", "size": "note_thumbnail"},
            ]

        # 共通スタイルで各アイテムを生成
        for item in state.creative_suite:
            item_results = self._generate_item(state, item)
            results.extend(item_results)

        return results

    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        return self.generate(state)

    def _generate_item(self, state: SessionState, item: dict) -> list:
        """個別アイテムの生成"""
        item_type = item.get("item_type", "")
        size_key = item.get("size", "instagram_portrait")
        count = item.get("count", 1)

        # ステートのコピーを作って個別生成
        # (実際のstateは共有するが、size/page_countだけ一時変更)
        original_size = state.size
        original_count = state.page_count
        original_slides = state.slides

        state.size = size_key
        state.page_count = count
        state.slides = []

        # コンテンツ生成
        if item_type == "instagram_carousel":
            slides = self.llm.generate_slide_contents(state.title or "", state.goal or state.title or "", count, state.style)
            state.slides = slides
        else:
            slides = self.llm.generate_slide_contents(state.title or "", state.goal or state.title or "", 1, state.style)
            state.slides = slides

        results = self.design_gen.generate(state)

        # ラベル更新
        for r in results:
            r["label"] = f"[{item.get('title', item_type)}] {r['label']}"

        # ステート復元
        state.size = original_size
        state.page_count = original_count
        state.slides = original_slides

        return results
