"""OpenAI LLM アダプタ（スケルトン - 将来用）"""
from adapters.base_llm import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI API を使用するLLMアダプタ（未実装）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # TODO: openai クライアント初期化

    def analyze_intent(self, user_text: str, context: dict) -> dict:
        raise NotImplementedError("OpenAI adapter is not yet implemented. Use mock mode.")

    def generate_response(self, prompt: str, context: dict) -> str:
        raise NotImplementedError("OpenAI adapter is not yet implemented. Use mock mode.")

    def extract_content_params(self, user_text: str, mode: str) -> dict:
        raise NotImplementedError("OpenAI adapter is not yet implemented. Use mock mode.")

    def generate_manga_script(self, theme: str, panel_count: int) -> list:
        raise NotImplementedError("OpenAI adapter is not yet implemented. Use mock mode.")

    def generate_slide_contents(self, goal: str, page_count: int, style: str) -> list:
        raise NotImplementedError("OpenAI adapter is not yet implemented. Use mock mode.")
