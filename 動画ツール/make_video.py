# -*- coding: utf-8 -*-
"""
スライドショー動画生成ツール（4:5 縦・フィード投稿向け）
複数画像 + キャプション → 字幕付きスライドショー動画(mp4)

使い方:
  1. input/ に画像を入れる（番号順に並ぶようファイル名を 01_, 02_ ... 推奨）
  2. input/slides.txt に「画像ファイル名 | キャプション」を1行ずつ書く
  3. python make_video.py   を実行
  4. output/result.mp4 が出来る

オプション:
  --sec 4      1枚あたりの表示秒数（デフォルト3）
  --fade 0.6   クロスフェード秒数（デフォルト0.5）
  --out xxx.mp4 出力ファイル名
"""
import argparse
import os
import subprocess
import sys
import tempfile
import textwrap
import glob
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def find_ffmpeg():
    """PATH に無くても winget でインストールした ffmpeg.exe を探す。"""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    pat = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages",
        "Gyan.FFmpeg*", "**", "ffmpeg.exe",
    )
    hits = glob.glob(pat, recursive=True)
    if hits:
        return hits[0]
    raise FileNotFoundError("ffmpeg が見つかりません。winget install Gyan.FFmpeg を実行してください。")


FFMPEG = find_ffmpeg()

# ---- 設定 ----
W, H = 1080, 1350           # 4:5 縦
FONT_PATH = r"C:\Windows\Fonts\meiryob.ttc"   # メイリオ太字
FONT_SIZE = 56
CAPTION_MAX_CHARS = 16      # 1行あたりの最大文字数（日本語想定）
MARGIN = 60
HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(HERE, "input")
OUTPUT_DIR = os.path.join(HERE, "output")
SLIDES_TXT = os.path.join(INPUT_DIR, "slides.txt")


def load_slides():
    """slides.txt を読む。無ければ input/ の画像を名前順にキャプション空で使う。"""
    slides = []
    if os.path.exists(SLIDES_TXT):
        with open(SLIDES_TXT, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    name, cap = line.split("|", 1)
                    slides.append((name.strip(), cap.strip()))
                else:
                    slides.append((line.strip(), ""))
    else:
        exts = (".png", ".jpg", ".jpeg", ".webp")
        imgs = sorted(f for f in os.listdir(INPUT_DIR) if f.lower().endswith(exts))
        slides = [(f, "") for f in imgs]
    return slides


def render_frame(img_name, caption, idx):
    """1枚のフレーム(4:5)をPNGで描画して一時パスを返す。"""
    src_path = os.path.join(INPUT_DIR, img_name)
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"画像が見つかりません: {src_path}")

    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    src = Image.open(src_path).convert("RGB")
    # 背景: 画像を画面いっぱいにぼかして敷く（余白を埋める）
    bg = src.copy()
    bg_ratio = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * bg_ratio), int(bg.height * bg_ratio)))
    bg = bg.filter(ImageFilter.GaussianBlur(30))
    bx = (bg.width - W) // 2
    by = (bg.height - H) // 2
    canvas.paste(bg.crop((bx, by, bx + W, by + H)), (0, 0))
    # 背景を少し暗く
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    canvas = Image.blend(canvas, dark, 0.35)

    # 前景: 画像をフィット表示（上寄せ。下にキャプション領域を残す）
    fg_area_h = int(H * 0.72)
    fg = src.copy()
    fg_ratio = min(W / fg.width, fg_area_h / fg.height)
    fg = fg.resize((int(fg.width * fg_ratio), int(fg.height * fg_ratio)))
    fx = (W - fg.width) // 2
    fy = (fg_area_h - fg.height) // 2 + 20
    canvas.paste(fg, (fx, fy))

    # キャプション帯
    if caption:
        draw = ImageDraw.Draw(canvas, "RGBA")
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        lines = []
        for para in caption.split("\\n"):
            lines.extend(textwrap.wrap(para, CAPTION_MAX_CHARS) or [""])
        line_h = FONT_SIZE + 18
        block_h = line_h * len(lines)
        band_top = H - block_h - MARGIN * 2
        # 半透明の黒帯
        draw.rectangle([0, band_top, W, H], fill=(0, 0, 0, 170))
        y = band_top + MARGIN
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln, font=font)
            tw = bbox[2] - bbox[0]
            x = (W - tw) // 2
            # 縁取り
            for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
            y += line_h

    tmp = os.path.join(tempfile.gettempdir(), f"_slide_{idx:03d}.png")
    canvas.save(tmp)
    return tmp


def build_video(frames, sec, fade, out_path):
    """フレーム群をクロスフェードで連結して mp4 出力。"""
    n = len(frames)
    # 各画像を sec 秒の動画クリップにし、xfade で連結
    inputs = []
    for fr in frames:
        inputs += ["-loop", "1", "-t", str(sec), "-i", fr]

    if n == 1:
        cmd = [FFMPEG, "-y"] + inputs + [
            "-vf", "format=yuv420p", "-r", "30", out_path,
        ]
    else:
        filters = []
        prev = "0:v"
        offset = sec - fade
        for i in range(1, n):
            out_label = f"v{i}"
            filters.append(
                f"[{prev}][{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{out_label}]"
            )
            prev = out_label
            offset += sec - fade
        filter_complex = ";".join(filters) + f";[{prev}]format=yuv420p[outv]"
        cmd = [FFMPEG, "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-r", "30", out_path,
        ]

    print("ffmpeg 実行中...")
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sec", type=float, default=3.0, help="1枚あたりの秒数")
    ap.add_argument("--fade", type=float, default=0.5, help="クロスフェード秒数")
    ap.add_argument("--out", default="result.mp4", help="出力ファイル名")
    args = ap.parse_args()

    slides = load_slides()
    if not slides:
        print("input/ に画像がありません。画像を入れてから再実行してください。")
        sys.exit(1)

    print(f"{len(slides)} 枚のスライドを描画します...")
    frames = []
    for i, (name, cap) in enumerate(slides):
        frames.append(render_frame(name, cap, i))
        print(f"  [{i+1}/{len(slides)}] {name}  {cap[:20]}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, args.out)
    build_video(frames, args.sec, args.fade, out_path)
    print(f"\\n完成: {out_path}")


if __name__ == "__main__":
    main()
