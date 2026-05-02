"""プロンプト生成エンジン - メインロジック"""
from prompt_generators.presets import (
    STYLE_PRESETS, STRUCTURE_PRESETS, GENRE_PRESETS,
    ASPECT_RATIO_PRESETS, PURPOSE_PRESETS
)
from prompt_generators.formatter import PromptFormatter


class PromptEngine:
    """画像生成AI用プロンプトを生成するエンジン"""

    def __init__(self):
        self.formatter = PromptFormatter()

    def generate(self, config: dict) -> dict:
        """
        設定からプロンプトを生成

        Args:
            config: {
                "purpose": str,
                "aspect_ratio": str,
                "count": int,
                "genre": str,
                "genre_custom": str,
                "structure": str,
                "style": str,
                "output_format": str,  # "individual" or "grid"
                "slides": [{"title": str, "text": str}, ...],
                "character": {"description": str, "image_path": str},
            }

        Returns:
            {
                "prompts": [
                    {
                        "index": int,
                        "title": str,
                        "midjourney": str,
                        "sd_positive": str,
                        "sd_negative": str,
                        "sd_settings": dict,
                        "nb2_positive": str,
                        "nb2_negative": str,
                        "dalle": str,
                    }, ...
                ],
                "output_format": str,
                "grid_prompt": {...} or None,
            }
        """
        purpose = config.get("purpose", "carousel")
        aspect_ratio = config.get("aspect_ratio", "1:1")
        count = config.get("count", 1)
        genre = config.get("genre", "business")
        genre_custom = config.get("genre_custom", "")
        structure = config.get("structure", "infographic")
        style = config.get("style", "anime")
        output_format = config.get("output_format", "individual")
        slides = config.get("slides", [])
        character = config.get("character", {})

        # スライドが足りない場合は空で埋める
        while len(slides) < count:
            slides.append({"title": f"スライド {len(slides) + 1}", "text": ""})

        # 各スライドのプロンプトを生成
        prompts = []
        for i in range(count):
            slide = slides[i] if i < len(slides) else {"title": "", "text": ""}
            prompt_data = self._build_prompt(
                index=i,
                slide=slide,
                purpose=purpose,
                aspect_ratio=aspect_ratio,
                genre=genre,
                genre_custom=genre_custom,
                structure=structure,
                style=style,
                character=character,
                total_count=count,
            )
            prompts.append(prompt_data)

        result = {
            "prompts": prompts,
            "output_format": output_format,
            "grid_prompt": None,
        }

        # グリッド出力の場合、1枚にまとめるプロンプトも生成
        if output_format == "grid" and count > 1:
            result["grid_prompt"] = self._build_grid_prompt(
                prompts, aspect_ratio, style, structure, count
            )

        return result

    def _build_prompt(self, index: int, slide: dict, purpose: str,
                      aspect_ratio: str, genre: str, genre_custom: str,
                      structure: str, style: str, character: dict,
                      total_count: int) -> dict:
        """個別プロンプトを組み立てる"""

        # 基本要素を収集
        style_data = STYLE_PRESETS.get(style, STYLE_PRESETS["anime"])
        structure_data = STRUCTURE_PRESETS.get(structure, STRUCTURE_PRESETS["infographic"])
        genre_data = GENRE_PRESETS.get(genre, GENRE_PRESETS["business"])
        ar_data = ASPECT_RATIO_PRESETS.get(aspect_ratio, ASPECT_RATIO_PRESETS["1:1"])

        # ジャンルヒント
        genre_hint = genre_custom if genre == "custom" and genre_custom else genre_data["hint"]

        # スライドコンテンツ
        slide_title = slide.get("title", "")
        slide_text = slide.get("text", "")

        # コンテンツ説明を構築
        content_desc = self._build_content_description(
            slide_title, slide_text, purpose, index, total_count
        )

        # キャラクター強調記述
        char_desc = ""
        mj_char_params = ""
        if character.get("description"):
            char_desc = character["description"]
            # SD向けにキャラ描写を強くする
            char_desc = f"highly detailed character design, {char_desc}"
        
        if character.get("image_path"):
            # Midjourney v6 cref (character reference) を追加. フルURLにします。
            url_path = character["image_path"]
            if not url_path.startswith("http"):
                url_path = f"http://127.0.0.1:5050{url_path}"
            mj_char_params = f" --cref {url_path} --cw 100"

        # さらにリッチなプロンプトにするための追加タグ
        cinematic_tags = "cinematic lighting, dynamic composition, intricate details, sharp focus, stunning visuals"

        # === Midjourney プロンプト生成 ===
        mj_prompt = self.formatter.format_midjourney(
            content=content_desc,
            style_hint=style_data["mj_hint"],
            structure_hint=structure_data["prompt_hint"],
            genre_hint=genre_hint,
            character=char_desc,
            ar_param=ar_data["mj"] + mj_char_params,
        )

        # === Stable Diffusion プロンプト生成 ===
        sd_positive = self.formatter.format_sd_positive(
            content=f"{content_desc}, {cinematic_tags}",
            style_hint=style_data["sd_hint"],
            structure_hint=structure_data["prompt_hint"],
            genre_hint=genre_hint,
            character=char_desc,
        )
        sd_negative = self.formatter.format_sd_negative(
            base_negative=style_data.get("sd_neg", ""),
            has_character_image=bool(character.get("image_path")),
        )
        sd_settings = {
            "width": ar_data["sd_w"],
            "height": ar_data["sd_h"],
            "steps": 30,
            "cfg_scale": 7.0,
            "sampler": "DPM++ 2M Karras",
            "model": style_data.get("sd_model", "SDXL"),
        }
        
        if character.get("image_path"):
            url_path = character["image_path"]
            if not url_path.startswith("http"):
                url_path = f"http://127.0.0.1:5050{url_path}"
            sd_settings["controlnet_image"] = url_path

        # === nanobanana2 プロンプト生成 ===
        nb2_positive = self.formatter.format_nb2_positive(
            content=f"{content_desc}, {cinematic_tags}",
            style_hint=style_data["sd_hint"],
            structure_hint=structure_data["prompt_hint"],
            genre_hint=genre_hint,
            character=char_desc,
        )
        nb2_negative = self.formatter.format_nb2_negative(
            base_negative=style_data.get("sd_neg", ""),
            has_character_image=bool(character.get("image_path")),
        )

        # === DALL-E プロンプト生成 ===
        dalle_prompt = self.formatter.format_dalle(
            content=content_desc,
            style_hint=style_data["mj_hint"],
            structure_hint=structure_data["prompt_hint"],
            genre_hint=genre_hint,
            character=char_desc,
            size=ar_data["dalle"],
        )

        return {
            "index": index,
            "title": slide_title or f"Image {index + 1}",
            "midjourney": mj_prompt,
            "sd_positive": sd_positive,
            "sd_negative": sd_negative,
            "sd_settings": sd_settings,
            "nb2_positive": nb2_positive,
            "nb2_negative": nb2_negative,
            "dalle": dalle_prompt,
            "dalle_size": ar_data["dalle"],
        }

    def _build_content_description(self, title: str, text: str,
                                    purpose: str, index: int,
                                    total_count: int) -> str:
        """スライド内容からコンテンツ記述を生成"""
        parts = []

        # 用途に応じたフレーミング
        purpose_data = PURPOSE_PRESETS.get(purpose, {})
        if purpose == "carousel" and total_count > 1:
            parts.append(f"slide {index + 1} of {total_count} in a carousel series")
        elif purpose == "thumbnail":
            parts.append("eye-catching thumbnail image")
        elif purpose == "manga":
            panel_names = ["introduction panel", "development panel",
                          "climax panel", "conclusion panel"]
            if index < len(panel_names):
                parts.append(panel_names[index])
            else:
                parts.append(f"manga panel {index + 1}")
        elif purpose == "character_sheet":
            parts.append(f"character sheet, pose variation {index + 1}")
        elif purpose == "service_intro":
            parts.append("service introduction visual")
        elif purpose == "story":
            parts.append(f"scene {index + 1} of {total_count} in a visual story")

        # タイトルとテキスト
        if title:
            parts.append(title)
        if text:
            parts.append(text)

        return ", ".join(parts) if parts else "creative visual content"

    def _build_grid_prompt(self, prompts: list, aspect_ratio: str,
                           style: str, structure: str, count: int) -> dict:
        """グリッド出力用のプロンプト"""
        style_data = STYLE_PRESETS.get(style, STYLE_PRESETS["anime"])
        ar_data = ASPECT_RATIO_PRESETS.get(aspect_ratio, ASPECT_RATIO_PRESETS["1:1"])

        # 各スライドの要約
        slide_descs = []
        for p in prompts:
            slide_descs.append(p["title"])
        slides_text = " | ".join(slide_descs)

        # グリッドレイアウトの指定
        if count <= 4:
            grid = f"{count}-panel grid layout, {count} equal sections"
        elif count <= 6:
            grid = f"2x3 grid layout, 6 panels"
        else:
            grid = f"grid layout with {count} panels"

        mj = (
            f"{grid}, each panel showing different scene, "
            f"[{slides_text}], "
            f"consistent style throughout, {style_data['mj_hint']}, "
            f"{ar_data['mj']} --v 6"
        )

        sd_pos = (
            f"{grid}, multiple scenes in one image, "
            f"({slides_text}), consistent art style, "
            f"{style_data['sd_hint']}, masterpiece, best quality"
        )

        dalle = (
            f"A single image divided into {count} equal panels arranged in a grid. "
            f"Each panel depicts a different scene: {slides_text}. "
            f"{style_data['mj_hint']}, consistent style across all panels."
        )

        return {
            "midjourney": mj,
            "sd_positive": sd_pos,
            "sd_negative": style_data.get("sd_neg", "") + ", inconsistent style, different art styles between panels",
            "sd_settings": {
                "width": ar_data["sd_w"],
                "height": ar_data["sd_h"],
                "steps": 30,
                "cfg_scale": 7.0,
                "sampler": "DPM++ 2M Karras",
                "model": style_data.get("sd_model", "SDXL"),
            },
            "nb2_positive": sd_pos,
            "nb2_negative": style_data.get("sd_neg", "") + ", inconsistent style, different art styles between panels, worst quality, low quality",
            "dalle": dalle,
            "dalle_size": ar_data["dalle"],
        }
