"""セッション状態スキーマ定義"""
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CharacterSettings:
    """固定キャラクター設定"""
    enabled: bool = False
    name: str = ""
    appearance: str = ""
    hair: str = ""
    outfit: str = ""
    colors: list = field(default_factory=list)
    personality: str = ""
    expression_style: str = ""
    pose_style: str = ""
    reference_notes: str = ""
    ng_items: list = field(default_factory=list)
    worldview_notes: str = ""


@dataclass
class BrandSettings:
    """ブランド設定"""
    brand_name: str = ""
    brand_colors: list = field(default_factory=list)
    font_style: str = ""
    visual_rules: list = field(default_factory=list)


@dataclass
class Panel:
    """漫画コマ"""
    index: int = 0
    role: str = ""  # 導入/展開/ため/オチ
    summary: str = ""
    dialogue: str = ""
    scene_description: str = ""
    expression_note: str = ""
    balloon_position: str = "top-right"


@dataclass
class Slide:
    """カルーセルスライド"""
    index: int = 0
    title: str = ""
    subtitle: str = ""
    body_text: str = ""
    layout: str = "center"
    accent_color: str = ""
    icon: str = ""


@dataclass
class CreativeSuiteItem:
    """世界観統一セットの1アイテム"""
    item_type: str = ""  # youtube_thumbnail, instagram_carousel, service_intro
    title: str = ""
    size: str = ""
    generated_svg: str = ""


@dataclass
class SessionState:
    """セッション全体の状態"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # モード
    mode: str = ""  # design | fixed_character_series | four_panel_manga | one_page_manga | creative_suite

    # 基本情報
    goal: str = ""
    platform: str = ""
    size: str = ""
    style: str = ""
    tone: str = ""
    worldview: str = ""
    genre: str = ""

    # コンテンツ
    title: str = ""
    subtitle: str = ""
    body_text: str = ""
    cta: str = ""
    page_count: int = 1

    # 配色
    color_scheme: str = ""
    primary_color: str = ""
    secondary_color: str = ""
    accent_color: str = ""
    background_color: str = ""

    # スライド/コマ
    slides: list = field(default_factory=list)
    panels: list = field(default_factory=list)

    # 世界観統一セット
    creative_suite: list = field(default_factory=list)

    # キャラクター・ブランド
    character_settings: dict = field(default_factory=lambda: asdict(CharacterSettings()))
    brand_settings: dict = field(default_factory=lambda: asdict(BrandSettings()))

    # 制約・履歴
    fixed_constraints: list = field(default_factory=list)
    change_requests: list = field(default_factory=list)
    references: list = field(default_factory=list)

    # 出力
    output_format: str = "svg"
    generated_content: list = field(default_factory=list)  # 生成済みSVG/HTML
    version: int = 1

    # 会話
    messages: list = field(default_factory=list)
    pending_questions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """辞書に変換"""
        self.updated_at = time.time()
        return asdict(self)

    def to_json(self) -> str:
        """JSON文字列に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """辞書から復元"""
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    @classmethod
    def from_json(cls, json_str: str) -> "SessionState":
        """JSON文字列から復元"""
        return cls.from_dict(json.loads(json_str))

    def update(self, updates: dict):
        """差分更新"""
        for key, value in updates.items():
            if hasattr(self, key) and value is not None and value != "":
                setattr(self, key, value)
        self.updated_at = time.time()

    def add_message(self, role: str, content: str):
        """メッセージ追加"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def get_summary(self) -> str:
        """セッション概要を返す"""
        parts = []
        if self.mode:
            parts.append(f"モード: {self.mode}")
        if self.goal:
            parts.append(f"目的: {self.goal}")
        if self.title:
            parts.append(f"タイトル: {self.title}")
        return " / ".join(parts) if parts else "新規セッション"


# サイズプリセット
SIZE_PRESETS = {
    "instagram_square": {"width": 1080, "height": 1080, "label": "Instagram正方形"},
    "instagram_portrait": {"width": 1080, "height": 1350, "label": "Instagramポートレート"},
    "instagram_story": {"width": 1080, "height": 1920, "label": "Instagramストーリー"},
    "youtube_thumbnail": {"width": 1280, "height": 720, "label": "YouTubeサムネイル"},
    "note_thumbnail": {"width": 1200, "height": 630, "label": "note/OGP"},
    "manga_4panel": {"width": 800, "height": 1200, "label": "4コマ漫画"},
    "manga_1page": {"width": 800, "height": 1100, "label": "1ページ漫画"},
}

# スタイルプリセット
STYLE_PRESETS = {
    "simple": {
        "label": "シンプル",
        "primary": "#2D3436",
        "secondary": "#636E72",
        "accent": "#0984E3",
        "background": "#FFFFFF",
        "font": "Noto Sans JP",
        "description": "洗練されたミニマルデザイン"
    },
    "pop": {
        "label": "ポップ",
        "primary": "#E17055",
        "secondary": "#FDCB6E",
        "accent": "#00B894",
        "background": "#FFF8F0",
        "font": "Noto Sans JP",
        "description": "明るく楽しい雰囲気"
    },
    "luxury": {
        "label": "高級感",
        "primary": "#2C2C54",
        "secondary": "#BFA14A",
        "accent": "#D4A574",
        "background": "#1A1A2E",
        "font": "Noto Serif JP",
        "description": "重厚で上品なデザイン"
    },
    "business": {
        "label": "ビジネス",
        "primary": "#1E3A5F",
        "secondary": "#4A90D9",
        "accent": "#27AE60",
        "background": "#F8F9FA",
        "font": "Noto Sans JP",
        "description": "信頼感のあるビジネス向け"
    },
    "friendly": {
        "label": "親しみやすい",
        "primary": "#5B2C6F",
        "secondary": "#F39C12",
        "accent": "#E74C3C",
        "background": "#FDF2E9",
        "font": "Noto Sans JP",
        "description": "温かみのあるフレンドリーなデザイン"
    }
}
