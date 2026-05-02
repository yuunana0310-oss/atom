"""ジェネレータ基底クラス"""
from abc import ABC, abstractmethod
from core.state_schema import SessionState


class BaseGenerator(ABC):
    """コンテンツジェネレータの抽象基底クラス"""

    @abstractmethod
    def generate(self, state: SessionState) -> list:
        """
        コンテンツを生成する

        Returns:
            list of dict: [{ "type": "svg"|"html", "content": str, "label": str, "size": dict }]
        """
        pass

    @abstractmethod
    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        pass

    def get_style_colors(self, style: str) -> dict:
        """スタイルプリセットの配色を取得"""
        from core.state_schema import STYLE_PRESETS
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["simple"])
        return {
            "primary": preset["primary"],
            "secondary": preset["secondary"],
            "accent": preset["accent"],
            "background": preset["background"],
            "font": preset.get("font", "Noto Sans JP"),
        }

    def get_size(self, size_key: str) -> dict:
        """サイズプリセットを取得"""
        from core.state_schema import SIZE_PRESETS
        return SIZE_PRESETS.get(size_key, SIZE_PRESETS["instagram_portrait"])

    def escape_svg_text(self, text: str) -> str:
        """SVG用テキストエスケープ"""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def wrap_text_lines(self, text: str, max_chars: int = 15) -> list:
        """テキストを改行で分割、長い行は折り返す"""
        lines = []
        for line in text.split("\n"):
            while len(line) > max_chars:
                lines.append(line[:max_chars])
                line = line[max_chars:]
            lines.append(line)
        return lines
