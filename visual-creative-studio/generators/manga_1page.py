"""1ページ漫画ジェネレータ"""
from generators.base_generator import BaseGenerator
from core.state_schema import SessionState
from adapters.mock_llm import MockLLM


class Manga1PageGenerator(BaseGenerator):
    """1ページ漫画ネーム風SVG生成"""

    def __init__(self):
        self.llm = MockLLM()

    def generate(self, state: SessionState) -> list:
        """1ページ漫画を生成"""
        panel_count = max(4, min(6, state.page_count if state.page_count > 1 else 5))

        if not state.panels:
            panels = self.llm.generate_manga_script(
                state.goal or state.title or "日常",
                panel_count
            )
            state.panels = panels

        colors = self.get_style_colors(state.style or "simple")
        svg = self._render_1page_svg(state.panels, state.title or "1ページ漫画", colors)

        return [{
            "type": "svg",
            "content": svg,
            "label": f"1ページ漫画: {state.title or '無題'}",
            "size": {"width": 800, "height": 1100, "label": "1ページ漫画"},
            "index": 0
        }]

    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        return self.generate(state)

    def _render_1page_svg(self, panels: list, title: str, colors: dict) -> str:
        """ネーム風1ページ漫画"""
        w, h = 800, 1100
        margin = 40
        title_h = 70
        content_h = h - title_h - margin * 2
        content_w = w - margin * 2

        panel_count = len(panels)
        panels_svg = ""

        # コマ割りレイアウトパターン
        if panel_count <= 4:
            layouts = self._layout_4panels(margin, title_h + margin, content_w, content_h)
        elif panel_count == 5:
            layouts = self._layout_5panels(margin, title_h + margin, content_w, content_h)
        else:
            layouts = self._layout_6panels(margin, title_h + margin, content_w, content_h)

        for i, panel in enumerate(panels[:len(layouts)]):
            lx, ly, lw, lh = layouts[i]
            dialogue = panel.get("dialogue", "")
            scene = panel.get("scene_description", "")
            role = panel.get("role", "")

            # コマ枠
            panels_svg += f'''
  <rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" fill="white" stroke="#222" stroke-width="2.5"/>'''

            # 場面説明（薄い背景テキスト）
            scene_lines = self.wrap_text_lines(scene, int(lw / 16))
            for j, line in enumerate(scene_lines[:2]):
                panels_svg += f'''
  <text x="{lx + lw/2}" y="{ly + 30 + j*20}" text-anchor="middle" fill="#CCC" font-size="13" font-family="'Noto Sans JP', sans-serif">{self.escape_svg_text(line)}</text>'''

            # 吹き出し
            if dialogue:
                bx = lx + lw * 0.5
                by = ly + lh * 0.5
                br = min(lw * 0.35, lh * 0.3)

                panels_svg += f'''
  <ellipse cx="{bx}" cy="{by}" rx="{br}" ry="{br * 0.7}" fill="white" stroke="#333" stroke-width="1.5"/>'''

                dialogue_lines = self.wrap_text_lines(dialogue, int(br / 10))
                for j, line in enumerate(dialogue_lines[:3]):
                    panels_svg += f'''
  <text x="{bx}" y="{by - len(dialogue_lines)*9 + j*22 + 10}" text-anchor="middle" fill="#333" font-size="15" font-weight="500" font-family="'Noto Sans JP', sans-serif">{self.escape_svg_text(line)}</text>'''

            # コマ番号
            panels_svg += f'''
  <circle cx="{lx + 18}" cy="{ly + 18}" r="12" fill="#333"/>
  <text x="{lx + 18}" y="{ly + 23}" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="'Noto Sans JP', sans-serif">{i+1}</text>'''

        title_escaped = self.escape_svg_text(title)

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="#F5F5F0"/>
  <rect x="{margin - 5}" y="{margin - 5}" width="{content_w + 10}" height="{h - margin*2 + 10}" fill="none" stroke="#333" stroke-width="3"/>
  <text x="{w//2}" y="{margin + 40}" text-anchor="middle" fill="#222" font-size="28" font-weight="bold" font-family="'Noto Sans JP', sans-serif">{title_escaped}</text>
  {panels_svg}
  <text x="{w//2}" y="{h - 15}" text-anchor="middle" fill="#CCC" font-size="11" font-family="'Noto Sans JP', sans-serif">ネーム / Visual Creative Studio</text>
</svg>'''

    def _layout_4panels(self, x, y, w, h):
        """4コマ レイアウト (2x2)"""
        gap = 8
        pw = (w - gap) / 2
        ph = (h - gap) / 2
        return [
            (x, y, pw, ph),
            (x + pw + gap, y, pw, ph),
            (x, y + ph + gap, pw, ph),
            (x + pw + gap, y + ph + gap, pw, ph),
        ]

    def _layout_5panels(self, x, y, w, h):
        """5コマ レイアウト (上2 + 中1大 + 下2)"""
        gap = 8
        pw = (w - gap) / 2
        row_h = (h - gap * 2) / 3
        return [
            (x, y, pw, row_h),
            (x + pw + gap, y, pw, row_h),
            (x, y + row_h + gap, w, row_h),  # 大コマ
            (x, y + row_h * 2 + gap * 2, pw, row_h),
            (x + pw + gap, y + row_h * 2 + gap * 2, pw, row_h),
        ]

    def _layout_6panels(self, x, y, w, h):
        """6コマ レイアウト (3x2)"""
        gap = 8
        pw = (w - gap) / 2
        ph = (h - gap * 2) / 3
        return [
            (x, y, pw, ph),
            (x + pw + gap, y, pw, ph),
            (x, y + ph + gap, pw, ph),
            (x + pw + gap, y + ph + gap, pw, ph),
            (x, y + ph * 2 + gap * 2, pw, ph),
            (x + pw + gap, y + ph * 2 + gap * 2, pw, ph),
        ]
