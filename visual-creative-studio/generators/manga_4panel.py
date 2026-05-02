"""4コマ漫画ジェネレータ"""
from generators.base_generator import BaseGenerator
from core.state_schema import SessionState
from adapters.mock_llm import MockLLM


class Manga4PanelGenerator(BaseGenerator):
    """4コマ漫画SVG生成"""

    def __init__(self):
        self.llm = MockLLM()

    def generate(self, state: SessionState) -> list:
        """4コマ漫画を生成"""
        # パネルスクリプト生成
        if not state.panels:
            panels = self.llm.generate_manga_script(
                state.goal or state.title or "日常",
                4
            )
            state.panels = panels

        # SVG生成
        colors = self.get_style_colors(state.style or "simple")
        svg = self._render_4panel_svg(state.panels, state.title or "4コマ漫画", colors)

        return [{
            "type": "svg",
            "content": svg,
            "label": f"4コマ漫画: {state.title or '無題'}",
            "size": {"width": 800, "height": 1200, "label": "4コマ漫画"},
            "index": 0
        }]

    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        target = change_request.get("target", "all")
        params = change_request.get("params", {})

        if target.startswith("panel_"):
            idx = int(target.replace("panel_", ""))
            if idx < len(state.panels):
                panel = state.panels[idx]
                if "panel_emphasis" in params:
                    if params["panel_emphasis"] == "dramatic_pause":
                        panel["expression_note"] = "強い溜め"
                        panel["scene_description"] = "【溜め】" + panel["scene_description"]

        return self.generate(state)

    def _render_4panel_svg(self, panels: list, title: str, colors: dict) -> str:
        """4コマ漫画SVGレンダリング"""
        w, h = 800, 1200
        panel_h = 230
        margin_top = 100
        margin_x = 40
        panel_w = w - margin_x * 2
        gap = 12

        panels_svg = ""
        for i, panel in enumerate(panels[:4]):
            py = margin_top + i * (panel_h + gap)
            role = panel.get("role", "")
            dialogue = panel.get("dialogue", "")
            scene = panel.get("scene_description", "")
            expression = panel.get("expression_note", "")

            # コマ枠
            panels_svg += f'''
  <rect x="{margin_x}" y="{py}" width="{panel_w}" height="{panel_h}" rx="4" fill="white" stroke="#333" stroke-width="2.5"/>'''

            # コマ番号ラベル
            role_colors = {"導入": "#4A90D9", "展開": "#27AE60", "ため": "#E67E22", "オチ": "#E74C3C"}
            role_color = role_colors.get(role, "#666")
            panels_svg += f'''
  <rect x="{margin_x}" y="{py}" width="60" height="28" fill="{role_color}" rx="0 4 0 0"/>
  <text x="{margin_x + 30}" y="{py + 20}" text-anchor="middle" fill="white" font-size="14" font-weight="bold" font-family="'Noto Sans JP', sans-serif">{role}</text>'''

            # 絵コンテエリア（左側）
            scene_x = margin_x + 20
            scene_y = py + 55
            panels_svg += f'''
  <rect x="{scene_x}" y="{scene_y}" width="{panel_w * 0.45}" height="{panel_h - 70}" rx="8" fill="#F8F8F8" stroke="#DDD" stroke-width="1" stroke-dasharray="4,4"/>
  <text x="{scene_x + panel_w * 0.225}" y="{scene_y + 30}" text-anchor="middle" fill="#999" font-size="14" font-family="'Noto Sans JP', sans-serif">🎨 絵コンテ</text>'''

            # 場面説明
            scene_lines = self.wrap_text_lines(scene, 12)
            for j, line in enumerate(scene_lines[:3]):
                panels_svg += f'''
  <text x="{scene_x + panel_w * 0.225}" y="{scene_y + 55 + j * 22}" text-anchor="middle" fill="#888" font-size="13" font-family="'Noto Sans JP', sans-serif">{self.escape_svg_text(line)}</text>'''

            # 表情メモ
            if expression:
                panels_svg += f'''
  <text x="{scene_x + panel_w * 0.225}" y="{scene_y + panel_h - 88}" text-anchor="middle" fill="{role_color}" font-size="12" font-family="'Noto Sans JP', sans-serif">表情: {self.escape_svg_text(expression)}</text>'''

            # 吹き出し（右側）
            balloon_x = margin_x + panel_w * 0.55
            balloon_y = py + 50
            balloon_w = panel_w * 0.40
            balloon_h = panel_h - 65

            dialogue_lines = self.wrap_text_lines(dialogue, 10)
            total_text_h = len(dialogue_lines) * 28
            text_start_y = balloon_y + (balloon_h - total_text_h) / 2 + 20

            # 吹き出し形状
            panels_svg += f'''
  <ellipse cx="{balloon_x + balloon_w/2}" cy="{balloon_y + balloon_h/2}" rx="{balloon_w/2}" ry="{balloon_h/2}" fill="white" stroke="#333" stroke-width="2"/>
  <polygon points="{balloon_x + 20},{balloon_y + balloon_h/2 + 10} {balloon_x - 5},{balloon_y + balloon_h/2 + 25} {balloon_x + 25},{balloon_y + balloon_h/2 + 25}" fill="white" stroke="#333" stroke-width="2"/>
  <line x1="{balloon_x + 20}" y1="{balloon_y + balloon_h/2 + 10}" x2="{balloon_x + 25}" y2="{balloon_y + balloon_h/2 + 25}" stroke="white" stroke-width="3"/>'''

            for j, line in enumerate(dialogue_lines[:4]):
                panels_svg += f'''
  <text x="{balloon_x + balloon_w/2}" y="{text_start_y + j * 28}" text-anchor="middle" fill="#333" font-size="18" font-weight="500" font-family="'Noto Sans JP', sans-serif">{self.escape_svg_text(line)}</text>'''

        title_escaped = self.escape_svg_text(title)

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="#FAFAFA"/>
  <text x="{w//2}" y="55" text-anchor="middle" fill="#333" font-size="32" font-weight="bold" font-family="'Noto Sans JP', sans-serif">{title_escaped}</text>
  <line x1="{w//2 - 100}" y1="72" x2="{w//2 + 100}" y2="72" stroke="#333" stroke-width="2"/>
  {panels_svg}
  <text x="{w//2}" y="{h - 25}" text-anchor="middle" fill="#CCC" font-size="12" font-family="'Noto Sans JP', sans-serif">Visual Creative Studio</text>
</svg>'''
