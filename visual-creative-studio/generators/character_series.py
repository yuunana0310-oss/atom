"""固定キャラクター複数枚ジェネレータ"""
from generators.base_generator import BaseGenerator
from core.state_schema import SessionState, STYLE_PRESETS


class CharacterSeriesGenerator(BaseGenerator):
    """固定キャラクター設定を保ったまま複数枚のカードを生成"""

    def generate(self, state: SessionState) -> list:
        """キャラクターカードシリーズを生成"""
        char = state.character_settings
        page_count = max(1, state.page_count)
        colors = self.get_style_colors(state.style or "pop")

        results = []
        poses = ["正面立ち", "斜めアングル", "アクション", "座り", "背面"]
        expressions = ["笑顔", "真剣", "驚き", "考え中", "照れ"]

        for i in range(page_count):
            pose = poses[i % len(poses)]
            expression = expressions[i % len(expressions)]
            svg = self._render_character_card(char, i, pose, expression, colors, state)
            results.append({
                "type": "svg",
                "content": svg,
                "label": f"キャラクターカード {i + 1}: {pose}",
                "size": {"width": 1080, "height": 1350, "label": "Instagram"},
                "index": i
            })

        return results

    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        return self.generate(state)

    def _render_character_card(self, char: dict, index: int, pose: str,
                               expression: str, colors: dict, state: SessionState) -> str:
        """キャラクターカードSVG"""
        w, h = 1080, 1350
        name = char.get("name", "キャラクター")
        appearance = char.get("appearance", "")
        hair = char.get("hair", "")
        outfit = char.get("outfit", "")
        personality = char.get("personality", "")
        char_colors = char.get("colors", [])

        # キャラカラー（設定があれば使用）
        char_primary = char_colors[0] if char_colors else colors["accent"]
        char_secondary = char_colors[1] if len(char_colors) > 1 else colors["secondary"]

        # キャラプロフィール情報
        info_lines = []
        if appearance:
            info_lines.append(f"見た目: {appearance}")
        if hair:
            info_lines.append(f"髪型: {hair}")
        if outfit:
            info_lines.append(f"服装: {outfit}")
        if personality:
            info_lines.append(f"性格: {personality}")

        info_svg = ""
        for j, line in enumerate(info_lines[:4]):
            info_svg += f'<text x="{w//2}" y="{h*0.72 + j*32}" text-anchor="middle" fill="{colors["primary"]}" font-size="20" font-family="\'Noto Sans JP\', sans-serif">{self.escape_svg_text(line[:25])}</text>\n'

        name_escaped = self.escape_svg_text(name)

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="char_bg_{index}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" style="stop-color:{colors['background']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#F0F0F0;stop-opacity:1"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#char_bg_{index})"/>

  <!-- キャラクターシルエットエリア -->
  <rect x="140" y="120" width="{w-280}" height="{h*0.48}" rx="20" fill="#F8F8F8" stroke="#E0E0E0" stroke-width="1" stroke-dasharray="8,4"/>
  <circle cx="{w//2}" cy="300" r="80" fill="{char_primary}" opacity="0.15"/>
  <circle cx="{w//2}" cy="300" r="60" fill="{char_primary}" opacity="0.1"/>
  <text x="{w//2}" y="290" text-anchor="middle" fill="{char_primary}" font-size="64">🧑‍🎨</text>
  <text x="{w//2}" y="340" text-anchor="middle" fill="#999" font-size="16" font-family="'Noto Sans JP', sans-serif">キャラクター描画エリア</text>

  <!-- ポーズ・表情メモ -->
  <rect x="180" y="420" width="{w-360}" height="70" rx="12" fill="{char_primary}" opacity="0.1"/>
  <text x="{w//2}" y="455" text-anchor="middle" fill="{char_primary}" font-size="20" font-weight="bold" font-family="'Noto Sans JP', sans-serif">ポーズ: {pose} / 表情: {expression}</text>
  <text x="{w//2}" y="480" text-anchor="middle" fill="{char_secondary}" font-size="14" font-family="'Noto Sans JP', sans-serif">カード {index + 1} / {state.page_count}</text>

  <!-- 固定設定バッジ -->
  <rect x="60" y="100" width="80" height="28" rx="14" fill="{char_primary}"/>
  <text x="100" y="119" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="'Noto Sans JP', sans-serif">固定</text>

  <!-- 名前 -->
  <text x="{w//2}" y="{h*0.58}" text-anchor="middle" fill="{colors['primary']}" font-size="42" font-weight="bold" font-family="'Noto Sans JP', sans-serif">{name_escaped}</text>
  <line x1="{w//2 - 80}" y1="{h*0.60}" x2="{w//2 + 80}" y2="{h*0.60}" stroke="{char_primary}" stroke-width="2"/>

  <!-- プロフィール -->
  <rect x="100" y="{h*0.64}" width="{w-200}" height="{h*0.22}" rx="16" fill="white" opacity="0.8"/>
  {info_svg}

  <!-- NG事項 -->
  <text x="{w//2}" y="{h*0.90}" text-anchor="middle" fill="#E74C3C" font-size="14" font-family="'Noto Sans JP', sans-serif">⚠ 固定設定: キャラクターの基本設定は全カードで統一</text>

  <text x="{w//2}" y="{h - 30}" text-anchor="middle" fill="#CCC" font-size="12" font-family="'Noto Sans JP', sans-serif">Visual Creative Studio</text>
</svg>'''
