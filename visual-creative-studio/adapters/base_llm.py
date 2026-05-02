"""LLM アダプタ基底クラス"""
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM アダプタの抽象基底クラス"""

    @abstractmethod
    def analyze_intent(self, user_text: str, context: dict) -> dict:
        """ユーザー入力の意図を解析"""
        pass

    @abstractmethod
    def generate_response(self, prompt: str, context: dict) -> str:
        """応答テキストを生成"""
        pass

    @abstractmethod
    def extract_content_params(self, user_text: str, mode: str) -> dict:
        """コンテンツ生成用パラメータを抽出"""
        pass

    @abstractmethod
    def generate_manga_script(self, theme: str, panel_count: int) -> list:
        """漫画スクリプトを生成"""
        pass

    @abstractmethod
    def generate_slide_contents(self, goal: str, page_count: int, style: str) -> list:
        """スライドコンテンツを生成"""
        pass
