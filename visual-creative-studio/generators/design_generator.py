"""デザイン生成 - カルーセル・サムネイル・サービス紹介"""
from generators.base_generator import BaseGenerator
from core.state_schema import SessionState, STYLE_PRESETS, SIZE_PRESETS
from adapters.mock_llm import MockLLM


class DesignGenerator(BaseGenerator):
    """デザインコンテンツ生成"""

    def __init__(self):
        self.llm = MockLLM()

    def generate(self, state: SessionState) -> list:
        """デザインコンテンツを生成"""
        # スライドコンテンツ生成（既に生成済みでなければ）
        if not state.slides:
            slides = self.llm.generate_slide_contents(
                title=state.title or "",
                goal=state.goal or state.title or "",
                page_count=state.page_count,
                style=state.style
            )
            state.slides = slides

        # SVG生成
        results = []
        colors = self.get_style_colors(state.style or "simple")
        size = self.get_size(state.size or "instagram_portrait")

        # カスタムカラーの上書き
        if state.primary_color:
            colors["primary"] = state.primary_color
        if state.secondary_color:
            colors["secondary"] = state.secondary_color
        if state.accent_color:
            colors["accent"] = state.accent_color
        if state.background_color:
            colors["background"] = state.background_color

        for slide in state.slides:
            svg = self._render_slide_svg(slide, colors, size, state)
            results.append({
                "type": "svg",
                "content": svg,
                "label": f"スライド {slide['index'] + 1}: {slide.get('title', '')}",
                "size": size,
                "index": slide["index"]
            })

        return results

    def update(self, state: SessionState, change_request: dict) -> list:
        """差分更新"""
        target = change_request.get("target", "all")
        params = change_request.get("params", {})

        # スタイル変更
        if "style" in params:
            state.style = params["style"]

        # 特定スライドの更新
        if target.startswith("slide_"):
            idx = int(target.replace("slide_", ""))
            if idx < len(state.slides):
                if "text_action" in params:
                    if params["text_action"] == "reduce":
                        slide = state.slides[idx]
                        body = slide.get("body_text", "")
                        # テキストを短縮
                        lines = body.split("\n")
                        if len(lines) > 1:
                            slide["body_text"] = "\n".join(lines[:len(lines)//2 + 1])

        return self.generate(state)

    def _render_slide_svg(self, slide: dict, colors: dict, size: dict, state: SessionState) -> str:
        """スライドSVGを生成"""
        w = size["width"]
        h = size["height"]
        style_name = state.style or "simple"

        title = self.escape_svg_text(slide.get("title", ""))
        subtitle = self.escape_svg_text(slide.get("subtitle", ""))
        body = slide.get("body_text", "")
        icon = slide.get("icon", "")
        idx = slide.get("index", 0)

        # スタイル別レンダリング
        if style_name == "luxury":
            return self._render_luxury(w, h, title, subtitle, body, icon, idx, colors, state)
        elif style_name == "pop":
            return self._render_pop(w, h, title, subtitle, body, icon, idx, colors, state)
        elif style_name == "business":
            return self._render_business(w, h, title, subtitle, body, icon, idx, colors, state)
        elif style_name == "friendly":
            return self._render_friendly(w, h, title, subtitle, body, icon, idx, colors, state)
        else:
            return self._render_simple(w, h, title, subtitle, body, icon, idx, colors, state)

    def _render_simple(self, w, h, title, subtitle, body, icon, idx, colors, state):
        """シンプルスタイル"""
        body_lines = self.wrap_text_lines(body, 18)
        body_svg = ""
        start_y = h * 0.58
        for i, line in enumerate(body_lines):
            body_svg += f'<text x="{w//2}" y="{start_y + i*42}" text-anchor="middle" fill="{colors["secondary"]}" font-size="28" font-family=\'Noto Sans JP\', sans-serif">{self.escape_svg_text(line)}</text>\n'

        page_indicator = ""
        if state.page_count > 1:
            dots = ""
            for p in range(state.page_count):
                fill = colors["accent"] if p == idx else "#DDD"
                dots += f'<circle cx="{w//2 - (state.page_count-1)*12 + p*24}" cy="{h - 50}" r="6" fill="{fill}"/>'
            page_indicator = dots

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="bg_simple_{idx}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" style="stop-color:{colors['background']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#F0F0F0;stop-opacity:1"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg_simple_{idx})" rx="0"/>
  <rect x="40" y="40" width="{w-80}" height="{h-80}" rx="20" fill="white" stroke="#E0E0E0" stroke-width="1"/>
  <line x1="{w//2 - 60}" y1="{h*0.48}" x2="{w//2 + 60}" y2="{h*0.48}" stroke="{colors['accent']}" stroke-width="3" stroke-linecap="round"/>
  <text x="{w//2}" y="{h*0.18}" text-anchor="middle" fill="{colors['accent']}" font-size="48" font-family="\'Noto Sans JP\', sans-serif" font-weight="400">{icon}</text>
  <text x="{w//2}" y="{h*0.32}" text-anchor="middle" fill="{colors['primary']}" font-size="42" font-weight="bold" font-family="\'Noto Sans JP\', sans-serif">{title}</text>
  <text x="{w//2}" y="{h*0.42}" text-anchor="middle" fill="{colors['secondary']}" font-size="24" font-family="\'Noto Sans JP\', sans-serif">{subtitle}</text>
  {body_svg}
  {page_indicator}
</svg>'''

    def _render_pop(self, w, h, title, subtitle, body, icon, idx, colors, state):
        """ポップスタイル"""
        body_lines = self.wrap_text_lines(body, 16)
        body_svg = ""
        start_y = h * 0.58
        for i, line in enumerate(body_lines):
            body_svg += f'<text x="{w//2}" y="{start_y + i*44}" text-anchor="middle" fill="{colors["primary"]}" font-size="30" font-weight="500" font-family="\'Noto Sans JP\', sans-serif">{self.escape_svg_text(line)}</text>\n'

        page_indicator = ""
        if state.page_count > 1:
            dots = ""
            for p in range(state.page_count):
                fill = colors["accent"] if p == idx else "#FFE0D0"
                dots += f'<rect x="{w//2 - (state.page_count-1)*14 + p*28 - 8}" y="{h - 55}" width="16" height="16" rx="4" fill="{fill}"/>'
            page_indicator = dots

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="bg_pop_{idx}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" style="stop-color:{colors['background']};stop-opacity:1"/>
      <stop offset="50%" style="stop-color:#FFF5EE;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#FFEFD5;stop-opacity:1"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg_pop_{idx})" rx="0"/>
  <circle cx="{w*0.85}" cy="{h*0.12}" r="60" fill="{colors['secondary']}" opacity="0.2"/>
  <circle cx="{w*0.15}" cy="{h*0.88}" r="45" fill="{colors['accent']}" opacity="0.15"/>
  <circle cx="{w*0.9}" cy="{h*0.75}" r="30" fill="{colors['primary']}" opacity="0.1"/>
  <rect x="60" y="{h*0.08}" width="{w-120}" height="{h*0.25}" rx="24" fill="white" opacity="0.8"/>
  <text x="{w//2}" y="{h*0.17}" text-anchor="middle" fill="{colors['primary']}" font-size="56" font-family="\'Noto Sans JP\', sans-serif">{icon}</text>
  <text x="{w//2}" y="{h*0.30}" text-anchor="middle" fill="{colors['primary']}" font-size="44" font-weight="800" font-family="\'Noto Sans JP\', sans-serif">{title}</text>
  <rect x="{w//2 - 100}" y="{h*0.37}" width="200" height="36" rx="18" fill="{colors['primary']}" opacity="0.9"/>
  <text x="{w//2}" y="{h*0.40 + 4}" text-anchor="middle" fill="white" font-size="20" font-weight="bold" font-family="\'Noto Sans JP\', sans-serif">{subtitle}</text>
  <rect x="80" y="{h*0.50}" width="{w-160}" height="{h*0.35}" rx="20" fill="white" opacity="0.6"/>
  {body_svg}
  {page_indicator}
</svg>'''

    def _render_luxury(self, w, h, title, subtitle, body, icon, idx, colors, state):
        """高級感スタイル"""
        body_lines = self.wrap_text_lines(body, 16)
        body_svg = ""
        start_y = h * 0.58
        for i, line in enumerate(body_lines):
            body_svg += f'<text x="{w//2}" y="{start_y + i*42}" text-anchor="middle" fill="#C8B88A" font-size="26" font-family="\'Noto Serif JP\', serif" letter-spacing="2">{self.escape_svg_text(line)}</text>\n'

        page_indicator = ""
        if state.page_count > 1:
            dots = ""
            for p in range(state.page_count):
                fill = colors["secondary"] if p == idx else "#333"
                dots += f'<rect x="{w//2 - (state.page_count-1)*16 + p*32 - 10}" y="{h - 55}" width="20" height="3" fill="{fill}"/>'
            page_indicator = dots

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="bg_lux_{idx}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" style="stop-color:#0D0D1A;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{colors['background']};stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="gold_{idx}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" style="stop-color:#BFA14A"/>
      <stop offset="50%" style="stop-color:#D4C17F"/>
      <stop offset="100%" style="stop-color:#8B7832"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg_lux_{idx})"/>
  <rect x="30" y="30" width="{w-60}" height="{h-60}" rx="0" fill="none" stroke="url(#gold_{idx})" stroke-width="1.5"/>
  <rect x="45" y="45" width="{w-90}" height="{h-90}" rx="0" fill="none" stroke="url(#gold_{idx})" stroke-width="0.5" opacity="0.5"/>
  <line x1="{w//2 - 80}" y1="{h*0.46}" x2="{w//2 + 80}" y2="{h*0.46}" stroke="url(#gold_{idx})" stroke-width="1"/>
  <text x="{w//2}" y="{h*0.19}" text-anchor="middle" fill="#D4C17F" font-size="48" font-family="\'Noto Serif JP\', serif">{icon}</text>
  <text x="{w//2}" y="{h*0.32}" text-anchor="middle" fill="#EEDDAA" font-size="40" font-weight="bold" font-family="\'Noto Serif JP\', serif" letter-spacing="4">{title}</text>
  <text x="{w//2}" y="{h*0.42}" text-anchor="middle" fill="#8B7D5E" font-size="22" font-family="\'Noto Serif JP\', serif" letter-spacing="3">{subtitle}</text>
  {body_svg}
  {page_indicator}
</svg>'''

    def _render_business(self, w, h, title, subtitle, body, icon, idx, colors, state):
        """ビジネススタイル"""
        body_lines = self.wrap_text_lines(body, 18)
        body_svg = ""
        start_y = h * 0.58
        for i, line in enumerate(body_lines):
            body_svg += f'<text x="{w//2}" y="{start_y + i*40}" text-anchor="middle" fill="{colors["primary"]}" font-size="26" font-family="\'Noto Sans JP\', sans-serif">{self.escape_svg_text(line)}</text>\n'

        page_indicator = ""
        if state.page_count > 1:
            dots = ""
            for p in range(state.page_count):
                fill = colors["accent"] if p == idx else "#CCC"
                dots += f'<circle cx="{w//2 - (state.page_count-1)*12 + p*24}" cy="{h - 50}" r="5" fill="{fill}"/>'
            page_indicator = dots

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="{colors['background']}"/>
  <rect x="0" y="0" width="{w}" height="8" fill="{colors['accent']}"/>
  <rect x="0" y="{h-8}" width="{w}" height="8" fill="{colors['accent']}"/>
  <rect x="60" y="{h*0.06}" width="{w-120}" height="{h*0.36}" rx="12" fill="white" stroke="#E8E8E8" stroke-width="1"/>
  <text x="{w//2}" y="{h*0.17}" text-anchor="middle" fill="{colors['accent']}" font-size="48" font-family="\'Noto Sans JP\', sans-serif">{icon}</text>
  <text x="{w//2}" y="{h*0.30}" text-anchor="middle" fill="{colors['primary']}" font-size="38" font-weight="bold" font-family="\'Noto Sans JP\', sans-serif">{title}</text>
  <rect x="{w//2 - 80}" y="{h*0.44}" width="160" height="30" rx="15" fill="{colors['primary']}"/>
  <text x="{w//2}" y="{h*0.46 + 6}" text-anchor="middle" fill="white" font-size="16" font-weight="bold" font-family="\'Noto Sans JP\', sans-serif">{subtitle}</text>
  {body_svg}
  {page_indicator}
</svg>'''

    def _render_friendly(self, w, h, title, subtitle, body, icon, idx, colors, state):
        """親しみやすいスタイル"""
        body_lines = self.wrap_text_lines(body, 16)
        body_svg = ""
        start_y = h * 0.58
        for i, line in enumerate(body_lines):
            body_svg += f'<text x="{w//2}" y="{start_y + i*44}" text-anchor="middle" fill="{colors["primary"]}" font-size="28" font-family="\'Noto Sans JP\', sans-serif">{self.escape_svg_text(line)}</text>\n'

        page_indicator = ""
        if state.page_count > 1:
            dots = ""
            for p in range(state.page_count):
                fill = colors["secondary"] if p == idx else "#E8D8C8"
                dots += f'<circle cx="{w//2 - (state.page_count-1)*12 + p*24}" cy="{h - 50}" r="7" fill="{fill}"/>'
            page_indicator = dots

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="bg_fr_{idx}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" style="stop-color:{colors['background']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#FFF0E0;stop-opacity:1"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg_fr_{idx})" rx="0"/>
  <circle cx="{w*0.5}" cy="{h*0.18}" r="60" fill="{colors['secondary']}" opacity="0.15"/>
  <text x="{w//2}" y="{h*0.20}" text-anchor="middle" fill="{colors['secondary']}" font-size="64" font-family="\'Noto Sans JP\', sans-serif">{icon}</text>
  <text x="{w//2}" y="{h*0.34}" text-anchor="middle" fill="{colors['primary']}" font-size="40" font-weight="bold" font-family="\'Noto Sans JP\', sans-serif">{title}</text>
  <rect x="{w//2 - 120}" y="{h*0.39}" width="240" height="32" rx="16" fill="{colors['accent']}" opacity="0.15"/>
  <text x="{w//2}" y="{h*0.41 + 5}" text-anchor="middle" fill="{colors['accent']}" font-size="20" font-weight="500" font-family="\'Noto Sans JP\', sans-serif">{subtitle}</text>
  {body_svg}
  {page_indicator}
</svg>'''
