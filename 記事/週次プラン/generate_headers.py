"""
note.com 見出し画像ジェネレーター
出力サイズ: 1280 x 670 px
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1280, 670
FONT_BOLD   = "C:/Windows/Fonts/YuGothB.ttc"
FONT_GOTHIC = "C:/Windows/Fonts/msgothic.ttc"


# ── ユーティリティ ────────────────────────────────────────

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def draw_text_centered(draw, text, y, font, color, width=W, x_offset=0):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2 + x_offset
    draw.text((x, y), text, font=font, fill=color)


def draw_text_left(draw, text, x, y, font, color):
    draw.text((x, y), text, font=font, fill=color)


def wrap_text(text, font, max_width, draw):
    """文字列を max_width に合わせて折り返す"""
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def draw_wrapped_centered(draw, text, y, font, color, max_width, line_gap=12):
    lines = wrap_text(text, font, max_width, draw)
    for line in lines:
        draw_text_centered(draw, line, y, font, color)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def gradient_bg(img, top_color, bottom_color):
    draw = ImageDraw.Draw(img)
    tr, tg, tb = top_color
    br, bg, bb = bottom_color
    for y in range(H):
        t = y / H
        r = int(tr + (br - tr) * t)
        g = int(tg + (bg - tg) * t)
        b = int(tb + (bb - tb) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def add_noise_lines(draw, color, alpha=30):
    """装飾ライン（グリッド風）"""
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(*color, alpha), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(*color, alpha), width=1)


def accent_bar(draw, x, y, w, h, color):
    draw.rectangle([x, y, x + w, y + h], fill=color)


# ── 画像01: 理学療法士がカルテを作り始めた話 ────────────────

def make_01():
    img = Image.new("RGB", (W, H))
    gradient_bg(img, (10, 18, 40), (20, 40, 80))

    # グリッド装飾
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, W, 60):
        od.line([(x, 0), (x, H)], fill=(255, 255, 255, 12))
    for y in range(0, H, 60):
        od.line([(0, y), (W, y)], fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # アクセントバー（左）
    accent_bar(draw, 100, 180, 5, 310, (0, 212, 255))

    # 上部タグ
    f_tag  = load_font(FONT_GOTHIC, 22)
    f_main = load_font(FONT_BOLD, 70)
    f_sub  = load_font(FONT_BOLD, 34)
    f_note = load_font(FONT_GOTHIC, 24)

    draw.text((120, 180), "開発日記 #01", font=f_tag, fill=(0, 212, 255))

    # メインコピー（2行）
    draw.text((120, 235), "理学療法士が", font=f_main, fill=(255, 255, 255))
    draw.text((120, 315), "カルテを作り始めた話", font=f_main, fill=(255, 255, 255))

    # サブコピー
    draw.text((122, 415), "完全オフライン × 患者データはローカルに完結", font=f_sub, fill=(160, 200, 255))

    # 下部ノート
    draw.text((122, 490), "Claude Code で作る PT × AI プロダクト開発記録", font=f_note, fill=(100, 150, 200))

    # 右下デコ（十字マーク）
    cx, cy, cs = 1100, 520, 60
    draw.line([(cx, cy - cs), (cx, cy + cs)], fill=(0, 212, 255, 180), width=4)
    draw.line([(cx - cs, cy), (cx + cs, cy)], fill=(0, 212, 255, 180), width=4)
    draw.ellipse([cx - cs - 10, cy - cs - 10, cx + cs + 10, cy + cs + 10],
                 outline=(0, 212, 255), width=2)

    img.save(os.path.join(OUT_DIR, "01_karte_hajimeta.png"))
    print("OK 01_karte_hajimeta.png")


# ── 画像02: AIツールに月2万円課金して ──────────────────────

def make_02():
    img = Image.new("RGB", (W, H))
    gradient_bg(img, (15, 12, 35), (35, 20, 60))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, W, 60):
        od.line([(x, 0), (x, H)], fill=(255, 255, 255, 10))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    f_tag  = load_font(FONT_GOTHIC, 22)
    f_en   = load_font(FONT_BOLD, 110)
    f_main = load_font(FONT_BOLD, 56)
    f_sub  = load_font(FONT_BOLD, 30)
    f_note = load_font(FONT_GOTHIC, 22)

    # ¥ 大きく
    draw.text((90, 140), "¥20,000 / 月", font=f_en, fill=(180, 130, 255))

    # アクセントバー
    accent_bar(draw, 90, 290, 600, 4, (180, 130, 255))

    draw.text((90, 310), "AI ツールに課金して", font=f_main, fill=(255, 255, 255))
    draw.text((90, 375), "残ったもの・やめたもの", font=f_main, fill=(255, 255, 255))

    draw.text((92, 455), "正直な使用感レポート", font=f_sub, fill=(180, 130, 255))
    draw.text((92, 500), "Claude / Perplexity / NotebookLM / ChatGPT / Midjourney…", font=f_note, fill=(150, 120, 200))

    # 右側 ○ デコ
    draw.ellipse([880, 120, 1160, 400], outline=(180, 130, 255), width=3)
    draw.ellipse([920, 160, 1120, 360], outline=(180, 130, 255, 80), width=2)
    draw_text_centered(draw, "正直", 230, load_font(FONT_BOLD, 60), (255, 255, 255),
                       width=240, x_offset=880)
    draw_text_centered(draw, "レポート", 300, load_font(FONT_BOLD, 36), (180, 130, 255),
                       width=240, x_offset=880)

    img.save(os.path.join(OUT_DIR, "02_ai_tool_kakkin.png"))
    print("OK 02_ai_tool_kakkin.png")


# ── 画像03: Claude Code でアプリを0から ────────────────────

def make_03():
    img = Image.new("RGB", (W, H))
    gradient_bg(img, (5, 20, 10), (10, 40, 20))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, W, 40):
        od.line([(x, 0), (x, H)], fill=(0, 255, 100, 8))
    for y in range(0, H, 40):
        od.line([(0, y), (W, y)], fill=(0, 255, 100, 8))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    f_tag   = load_font(FONT_GOTHIC, 20)
    f_code  = load_font(FONT_GOTHIC, 28)
    f_main  = load_font(FONT_BOLD, 64)
    f_sub   = load_font(FONT_BOLD, 32)
    f_badge = load_font(FONT_BOLD, 26)

    # ターミナル風の背景ボックス
    draw.rectangle([80, 120, 900, 300], fill=(0, 20, 5), outline=(0, 200, 80), width=2)
    draw.text((100, 130), "$ claude-code --start rehab-karte-app", font=f_code, fill=(0, 200, 80))
    draw.text((100, 170), "> Analyzing requirements...", font=f_code, fill=(0, 160, 60))
    draw.text((100, 210), "> Generating project structure... ✓", font=f_code, fill=(0, 200, 80))
    draw.text((100, 250), "> Ready. Let's build together.", font=f_code, fill=(180, 255, 180))

    # バッジ「300円」
    draw.rectangle([82, 318, 210, 358], fill=(0, 180, 80))
    draw.text((92, 322), "有料 300円", font=f_badge, fill=(255, 255, 255))

    # メインコピー
    draw.text((82, 370), "非エンジニアが実証", font=f_sub, fill=(100, 255, 150))
    draw.text((82, 415), "Claude Code でアプリを", font=f_main, fill=(255, 255, 255))
    draw.text((82, 490), "0 から作る手順", font=f_main, fill=(255, 255, 255))

    # プロンプト全公開タグ
    draw.text((84, 580), "# プロンプト全公開  # 非エンジニア  # Claude Code", font=f_tag, fill=(0, 200, 80))

    img.save(os.path.join(OUT_DIR, "03_claude_code_zero.png"))
    print("OK 03_claude_code_zero.png")


# ── 画像04: noteで売れる記事をAIで書く ─────────────────────

def make_04():
    img = Image.new("RGB", (W, H))
    gradient_bg(img, (25, 15, 5), (55, 30, 5))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, W, 70):
        od.line([(x, 0), (x, H)], fill=(255, 200, 100, 8))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    f_tag   = load_font(FONT_GOTHIC, 20)
    f_main  = load_font(FONT_BOLD, 66)
    f_sub   = load_font(FONT_BOLD, 32)
    f_badge = load_font(FONT_BOLD, 26)
    f_step  = load_font(FONT_GOTHIC, 24)

    # 左アクセントバー
    accent_bar(draw, 80, 130, 5, 380, (255, 160, 30))

    # バッジ
    draw.rectangle([100, 128, 228, 168], fill=(200, 100, 0))
    draw.text((110, 132), "有料 300円", font=f_badge, fill=(255, 255, 255))

    # タイトル
    draw.text((100, 185), "note で売れる記事を", font=f_main, fill=(255, 255, 255))
    draw.text((100, 262), "AI で書く方法", font=f_main, fill=(255, 200, 80))

    draw.text((102, 355), "使ったプロンプトをそのまま公開", font=f_sub, fill=(255, 160, 30))

    # 右側のステップ概要
    steps = [
        "Step 1  参考記事の構造をAIで分析",
        "Step 2  自分のテーマで再構築",
        "Step 3  タイトル10案を生成",
        "Step 4  採点→85点まで改善",
    ]
    sx, sy = 720, 160
    draw.rectangle([sx - 20, sy - 20, W - 60, sy + len(steps) * 52 + 10],
                   fill=(40, 20, 5), outline=(255, 160, 30), width=2)
    for i, s in enumerate(steps):
        draw.text((sx, sy + i * 52), s, font=f_step, fill=(255, 220, 150))

    draw.text((82, 570), "# AIライティング  # note攻略  # プロンプト公開", font=f_tag, fill=(255, 160, 30))

    img.save(os.path.join(OUT_DIR, "04_note_ai_writing.png"))
    print("OK 04_note_ai_writing.png")


# ── 実行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    make_01()
    make_02()
    make_03()
    make_04()
    print(f"\n完了: {OUT_DIR}")
