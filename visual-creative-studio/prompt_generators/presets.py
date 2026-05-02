"""プロンプト生成エンジン用のプリセットデータ"""

# ============================================================
# 用途プリセット
# ============================================================
PURPOSE_PRESETS = {
    "carousel": {"label": "カルーセル投稿", "desc": "Instagram等の複数枚スライド"},
    "thumbnail": {"label": "サムネイル", "desc": "YouTube/記事のアイキャッチ"},
    "manga": {"label": "漫画・コミック", "desc": "4コマ・1ページ漫画"},
    "character_sheet": {"label": "キャラクターシート", "desc": "キャラ設定・ポーズ集"},
    "service_intro": {"label": "サービス紹介", "desc": "LP・広告用ビジュアル"},
    "story": {"label": "ストーリー展開", "desc": "物語の場面展開"},
    "custom": {"label": "カスタム", "desc": "自由入力"},
}

# ============================================================
# キャンバス比率
# ============================================================
ASPECT_RATIO_PRESETS = {
    "1:1": {"label": "1:1（正方形）", "mj": "--ar 1:1", "sd_w": 1024, "sd_h": 1024, "dalle": "1024x1024"},
    "4:5": {"label": "4:5（Insta縦）", "mj": "--ar 4:5", "sd_w": 896, "sd_h": 1120, "dalle": "1024x1024"},
    "9:16": {"label": "9:16（ストーリー）", "mj": "--ar 9:16", "sd_w": 768, "sd_h": 1344, "dalle": "1024x1792"},
    "16:9": {"label": "16:9（YouTubeサムネ）", "mj": "--ar 16:9", "sd_w": 1344, "sd_h": 768, "dalle": "1792x1024"},
    "3:4": {"label": "3:4（ポートレート）", "mj": "--ar 3:4", "sd_w": 896, "sd_h": 1152, "dalle": "1024x1024"},
    "2:3": {"label": "2:3（漫画）", "mj": "--ar 2:3", "sd_w": 832, "sd_h": 1216, "dalle": "1024x1792"},
    "3:2": {"label": "3:2（ランドスケープ）", "mj": "--ar 3:2", "sd_w": 1216, "sd_h": 832, "dalle": "1792x1024"},
}

# ============================================================
# デザイン方向性・構造
# ============================================================
STRUCTURE_PRESETS = {
    "infographic": {
        "label": "インフォグラフィック",
        "prompt_hint": "infographic layout, data visualization, clean design, organized sections, icons and charts",
    },
    "editorial": {
        "label": "エディトリアル",
        "prompt_hint": "editorial design, magazine layout, elegant typography, sophisticated composition",
    },
    "comic": {
        "label": "コミック・漫画",
        "prompt_hint": "comic panel layout, manga style panels, speech bubbles, dynamic composition",
    },
    "illustration": {
        "label": "イラスト中心",
        "prompt_hint": "illustration focused, artistic composition, visual storytelling",
    },
    "photo_composite": {
        "label": "写真コンポジット",
        "prompt_hint": "photo composite, photographic elements, realistic rendering, studio lighting",
    },
    "minimal": {
        "label": "ミニマル",
        "prompt_hint": "minimalist design, lots of white space, simple composition, clean and modern",
    },
    "collage": {
        "label": "コラージュ",
        "prompt_hint": "collage style, mixed media, layered elements, creative arrangement",
    },
    "presentation_slide": {
        "label": "プレゼン資料・スライド調",
        "prompt_hint": "presentation slide layout, corporate pitch deck, keynote aesthetic, infographic charts, text placeholders, modern layout, plenty of negative space",
    },
    "sns_post": {
        "label": "SNS投稿・フィード",
        "prompt_hint": "social media post graphic, Instagram aesthetic, modern UI layout, marketing design graphic, beautiful typography layout, space for text",
    },
    "note_header": {
        "label": "Note/ブログ見出し用",
        "prompt_hint": "article header image, blog banner graphic, editorial web design, sophisticated layout, ample negative space for title",
    },
}

# ============================================================
# 画風（メインテイスト）
# ============================================================
STYLE_PRESETS = {
    "anime": {
        "label": "アニメ・イラスト",
        "mj_hint": "anime style, cel shading, vibrant colors, detailed illustration",
        "sd_hint": "anime, illustration, cel shaded, vibrant, detailed",
        "sd_neg": "photorealistic, 3d render, photograph",
        "sd_model": "animagine-xl / Anything V5",
    },
    "photorealistic": {
        "label": "フォトリアル",
        "mj_hint": "photorealistic, ultra detailed, professional photography, 8k",
        "sd_hint": "photorealistic, highly detailed, professional photo, 8k uhd, sharp focus",
        "sd_neg": "cartoon, anime, illustration, drawing, painting",
        "sd_model": "SDXL / Realistic Vision",
    },
    "watercolor": {
        "label": "水彩画風",
        "mj_hint": "watercolor painting, soft edges, flowing colors, artistic brushstrokes",
        "sd_hint": "watercolor painting, soft wash, flowing pigments, artistic, traditional media",
        "sd_neg": "digital art, sharp lines, photorealistic, 3d",
        "sd_model": "SDXL",
    },
    "flat_design": {
        "label": "フラットデザイン",
        "mj_hint": "flat design, vector style, bold colors, geometric shapes, simple illustration",
        "sd_hint": "flat design, vector art, bold solid colors, geometric, minimal shading",
        "sd_neg": "photorealistic, 3d, gradient shading, complex texture",
        "sd_model": "SDXL",
    },
    "3d_render": {
        "label": "3Dレンダリング",
        "mj_hint": "3D render, Blender style, soft lighting, clay render, isometric",
        "sd_hint": "3d render, blender, octane render, soft lighting, isometric view",
        "sd_neg": "2d, flat, painting, sketch, anime",
        "sd_model": "SDXL",
    },
    "ukiyoe": {
        "label": "浮世絵・和風",
        "mj_hint": "ukiyo-e style, Japanese woodblock print, traditional Japanese art, flat colors",
        "sd_hint": "ukiyo-e, woodblock print style, Japanese traditional art, flat color areas",
        "sd_neg": "photorealistic, western art, 3d, modern",
        "sd_model": "SDXL",
    },
    "cyberpunk": {
        "label": "サイバーパンク",
        "mj_hint": "cyberpunk aesthetic, neon lights, dark atmosphere, futuristic, high tech low life",
        "sd_hint": "cyberpunk, neon glow, dark cityscape, futuristic, holographic, rain",
        "sd_neg": "natural, pastoral, bright daylight, medieval",
        "sd_model": "SDXL / DreamShaper",
    },
    "oil_painting": {
        "label": "油絵風",
        "mj_hint": "oil painting, thick brushstrokes, rich textures, classical art style",
        "sd_hint": "oil painting, impasto, rich texture, classical art, canvas texture",
        "sd_neg": "digital art, anime, flat colors, photo",
        "sd_model": "SDXL",
    },
    "pixel_art": {
        "label": "ドット絵",
        "mj_hint": "pixel art, 16-bit style, retro game aesthetic, limited color palette",
        "sd_hint": "pixel art, 16bit, retro game style, limited palette, crisp pixels",
        "sd_neg": "high resolution, smooth, photorealistic, 3d",
        "sd_model": "SDXL",
    },
    "sketch": {
        "label": "スケッチ・線画",
        "mj_hint": "pencil sketch, hand drawn, line art, detailed hatching, sketchbook style",
        "sd_hint": "pencil sketch, line drawing, hand drawn, hatching, monochrome, on paper",
        "sd_neg": "colored, photorealistic, 3d, digital painting",
        "sd_model": "SDXL",
    },
    "taisho_roman": {
        "label": "大正ロマン風",
        "mj_hint": "Taisho Roman style, soft lighting, muted colors, retro nostalgic",
        "sd_hint": "Taisho Roman style, retro japanese clothes, nostalgic, soft colors",
        "sd_neg": "modern, futuristic, sci-fi",
        "sd_model": "animagine-xl",
    },
    "showa_retro": {
        "label": "昭和レトロ",
        "mj_hint": "Showa retro, warm lighting, nostalgic vintage Japan",
        "sd_hint": "Showa retro, 1980s, warm colors, nostalgic filtering",
        "sd_neg": "modern, high tech, futuristic",
        "sd_model": "SDXL",
    },
    "y2k": {
        "label": "Y2K風",
        "mj_hint": "Y2K aesthetic, chrome textures, vibrant colors, metallic, pop",
        "sd_hint": "Y2K aesthetic, 2000s, cyberpunk pop, chrome, shiny texture",
        "sd_neg": "antique, dark, medieval, dull colors",
        "sd_model": "SDXL",
    },
    "city_pop": {
        "label": "シティポップ風",
        "mj_hint": "city pop aesthetic, neon lights, soft glow, 80s anime style",
        "sd_hint": "city pop aesthetic, 1980s retro anime, pastel neon, nostalgic city",
        "sd_neg": "3d render, photorealistic, dark fantasy",
        "sd_model": "animagine-xl / SDXL",
    },
    "pop_art": {
        "label": "ポップアート",
        "mj_hint": "Pop Art style, halftone dots, bright colors, bold outlines",
        "sd_hint": "Pop Art style, halftone, bold outlines, vivid colors, comic style",
        "sd_neg": "photorealistic, oil painting, soft colors",
        "sd_model": "SDXL",
    },
    "art_nouveau": {
        "label": "アール・ヌーヴォー",
        "mj_hint": "Art Nouveau style, flowing lines, floral motifs, decorative",
        "sd_hint": "Art Nouveau, ornamental, flowing lines, intricate floral, Mucha style",
        "sd_neg": "minimalist, cyberpunk, blocky, abstract",
        "sd_model": "SDXL",
    },
    "sumi_e": {
        "label": "墨絵・水墨画風",
        "mj_hint": "sumi-e style, ink wash painting, black ink on white, soft gradients",
        "sd_hint": "sumi-e, ink wash painting, monochrome, traditional japanese ink, soft brush",
        "sd_neg": "vibrant colors, 3d, photorealistic, highly saturated",
        "sd_model": "SDXL",
    },
    "minimalism": {
        "label": "ミニマリズム",
        "mj_hint": "Minimalism, limited palette, simple shapes, plenty of negative space",
        "sd_hint": "Minimalism, minimal details, simple background, flat colors",
        "sd_neg": "complex, cluttered, highly detailed background",
        "sd_model": "SDXL",
    },
    "realistic_photo": {
        "label": "実写風",
        "mj_hint": "realistic photo, natural everyday life, soft lighting",
        "sd_hint": "realistic photo, photography, natural light, real life",
        "sd_neg": "anime, painting, cartoon, illustration, highly stylized",
        "sd_model": "Realistic Vision / SDXL",
    },
    "film_photography": {
        "label": "フィルム写真風",
        "mj_hint": "film photography style, film grain, vintage color processing, aesthetic",
        "sd_hint": "film photography, film grain, analog photo, fujifilm colors",
        "sd_neg": "digital, smooth, overly sharp, 3d render",
        "sd_model": "SDXL",
    },
    "35mm_film": {
        "label": "35mmフィルム",
        "mj_hint": "35mm film look, natural colors, authentic documentary feel, slight grain",
        "sd_hint": "35mm film look, analog photography, natural colors, detailed",
        "sd_neg": "digital illustration, painting, cartoon",
        "sd_model": "SDXL",
    },
    "disposable_camera": {
        "label": "使い捨てカメラ風",
        "mj_hint": "disposable camera look, harsh flash, low quality aesthetic, blurry edges, candid snapshot",
        "sd_hint": "disposable camera look, harsh camera flash, snapshot, candid, blurry edges",
        "sd_neg": "professional studio lighting, smooth, 4k",
        "sd_model": "SDXL",
    },
    "polaroid": {
        "label": "ポラロイド風",
        "mj_hint": "polaroid style, instant film, soft pastel tones, vintage borders, aged look",
        "sd_hint": "polaroid style, instant camera photo, vintage color fading, pastel tones",
        "sd_neg": "high contrast, sharp details, modern digital",
        "sd_model": "SDXL",
    },
    "vhs_look": {
        "label": "VHS風",
        "mj_hint": "VHS look, scanlines, distortion, chromatic aberration, retro video still",
        "sd_hint": "VHS look, crt scanlines, video distortion, chromatic aberration, highly textured",
        "sd_neg": "clean lines, sharp focus, 4k resolution",
        "sd_model": "SDXL",
    },
    "cinematic": {
        "label": "シネマ風",
        "mj_hint": "cinematic, wide aspect ratio, dramatic lighting, movie still, cinematic color grading",
        "sd_hint": "cinematic, movie still frame, dramatic lighting, highly detailed background, teal and orange",
        "sd_neg": "flat lighting, plain background, simple, cartoon",
        "sd_model": "SDXL",
    },
    "documentary": {
        "label": "ドキュメンタリー風",
        "mj_hint": "documentary style photo, raw reality, candid, natural light, unposed",
        "sd_hint": "documentary style photo, photojournalism, candid shot, natural lighting",
        "sd_neg": "studio lighting, posed, artificial, illustration",
        "sd_model": "Realistic Vision",
    },
    "bw_photo": {
        "label": "モノクロ写真",
        "mj_hint": "black and white photo, high contrast, artistic monochrome, dramatic shadow",
        "sd_hint": "black and white photography, monochrome, high contrast, shades of gray",
        "sd_neg": "color, colorful, painting",
        "sd_model": "SDXL",
    },
    "sepia": {
        "label": "セピア調",
        "mj_hint": "sepia tone photo, nostalgic, old history, warm brownish tint",
        "sd_hint": "sepia tone, nostalgic photography, vintage brown filter, aged",
        "sd_neg": "vivid colors, modern, cyberpunk",
        "sd_model": "SDXL",
    },
    "shallow_dof": {
        "label": "被写界深度浅め",
        "mj_hint": "shallow depth of field, blurred background, bokeh, focused subject, macro photography features",
        "sd_hint": "shallow depth of field, blurred background, bokeh, dslr, sharp focus on subject",
        "sd_neg": "deep depth of field, everything in focus, flat",
        "sd_model": "SDXL",
    },
    "backlight": {
        "label": "逆光",
        "mj_hint": "backlight, silhouette elements, lens flare, glowing edges, dramatic lighting from behind",
        "sd_hint": "backlighting, lens flare, glowing contours, dramatic light from behind, sunbeams",
        "sd_neg": "flat lighting, front light, dark",
        "sd_model": "SDXL",
    },
    "soft_focus": {
        "label": "ソフトフォーカス",
        "mj_hint": "soft focus, dreamy look, ethereal, soft glowing light, blurred details",
        "sd_hint": "soft focus, dreamy aesthetics, ethereal lighting, gentle blur",
        "sd_neg": "sharp details, high contrast, harsh lighting",
        "sd_model": "SDXL",
    },
}

# ============================================================
# ジャンル・世界観
# ============================================================
GENRE_PRESETS = {
    "business": {"label": "ビジネス・テック", "hint": "corporate, tech, modern office, professional"},
    "fantasy": {"label": "ファンタジー", "hint": "fantasy world, magical, enchanted, mythical creatures"},
    "scifi": {"label": "SF・未来", "hint": "science fiction, futuristic, space, advanced technology"},
    "nature": {"label": "ナチュラル・オーガニック", "hint": "natural, organic, earth tones, botanical"},
    "cute": {"label": "かわいい・ポップ", "hint": "kawaii, cute, pastel colors, playful, adorable"},
    "dark": {"label": "ダーク・ゴシック", "hint": "dark gothic, moody, dramatic shadows, mysterious"},
    "retro": {"label": "レトロ・ヴィンテージ", "hint": "retro, vintage, nostalgic, old school, aged"},
    "elegant": {"label": "エレガント・高級", "hint": "elegant, luxury, premium, gold accents, sophisticated"},
    "japanese": {"label": "和風・日本", "hint": "Japanese aesthetic, wabi-sabi, zen, traditional Japan"},
    "street": {"label": "ストリート・グランジ", "hint": "street art, graffiti, urban, grungy, raw"},
    "custom": {"label": "カスタム", "hint": ""},
}

# ============================================================
# 出力フォーマット
# ============================================================
OUTPUT_FORMAT = {
    "individual": {"label": "個別出力", "desc": "1枚ずつ独立した画像として出力"},
    "grid": {"label": "グリッド分割", "desc": "1枚の画像に分割配置して出力"},
}
