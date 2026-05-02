"""プロンプトフォーマッタ - 各AIプラットフォーム向けのフォーマット変換"""


class PromptFormatter:
    """Midjourney / Stable Diffusion / DALL-E 向けフォーマット"""

    # 品質ブースター
    MJ_QUALITY = "high quality, detailed"
    SD_QUALITY = "masterpiece, best quality, highly detailed"
    SD_BASE_NEGATIVE = (
        "worst quality, low quality, blurry, deformed, disfigured, "
        "bad anatomy, bad proportions, extra limbs, mutated, "
        "watermark, signature, text, logo, username"
    )

    def format_midjourney(self, content: str, style_hint: str,
                          structure_hint: str, genre_hint: str,
                          character: str, ar_param: str) -> str:
        """Midjourney形式のプロンプト生成"""
        parts = []

        # メインコンテンツ
        if content:
            parts.append(content)

        # キャラクター
        if character:
            parts.append(character)

        # 構造
        if structure_hint:
            parts.append(structure_hint)

        # ジャンル・世界観
        if genre_hint:
            parts.append(genre_hint)

        # 画風
        if style_hint:
            parts.append(style_hint)

        # 品質
        parts.append(self.MJ_QUALITY)

        prompt = ", ".join(parts)

        # パラメータ追加
        params = [ar_param, "--v 6", "--style raw"]
        prompt += " " + " ".join(params)

        return prompt

    def format_sd_positive(self, content: str, style_hint: str,
                           structure_hint: str, genre_hint: str,
                           character: str) -> str:
        """Stable Diffusion positive prompt生成"""
        parts = []

        # 品質タグ
        parts.append(self.SD_QUALITY)

        # メインコンテンツ
        if content:
            parts.append(content)

        # キャラクター
        if character:
            parts.append(f"(solo:1.1), (focus on {character}:1.4), detailed face, expressive eyes, vibrant hair")

        # 構造
        if structure_hint:
            parts.append(structure_hint)

        # ジャンル
        if genre_hint:
            parts.append(genre_hint)

        # 画風
        if style_hint:
            parts.append(style_hint)

        return ", ".join(parts)

    def format_sd_negative(self, base_negative: str = "", has_character_image: bool = False) -> str:
        """Stable Diffusion negative prompt生成"""
        parts = [self.SD_BASE_NEGATIVE]
        if base_negative:
            parts.append(base_negative)
            
        if has_character_image:
            parts.append("reference background, reference style bleed, original background context")
            
        return ", ".join(parts)

    def format_dalle(self, content: str, style_hint: str,
                     structure_hint: str, genre_hint: str,
                     character: str, size: str) -> str:
        """DALL-E形式のプロンプト生成（自然言語文の日本語フォーマット）"""
        parts = ["以下の条件で画像を生成してください。"]

        if content:
            parts.append(f"[内容・テーマ]: {content}")

        if character:
            parts.append(f"[キャラクター]: {character}")

        if structure_hint:
            parts.append(f"[構図・構造]: {structure_hint}")

        if genre_hint:
            parts.append(f"[世界観・ジャンル]: {genre_hint}")

        if style_hint:
            parts.append(f"[画風・スタイル]: {style_hint}")

        parts.append(f"[画像サイズ]: {size}")
        
        if character:
            parts.append("※【重要】添付画像がある場合、キャラクター（人物の顔・特徴・服装など）の情報のみを参考にしてください。")
            parts.append("※添付画像の背景や、指定したテキスト以外の余分な要素は一切読み取ったり反映したりしないでください。")

        parts.append("※プロフェッショナルで高品質なアートワークとして出力してください。")

        return "\n".join(parts)

    def format_nb2_positive(self, content: str, style_hint: str,
                            structure_hint: str, genre_hint: str,
                            character: str) -> str:
        """nanobanana2向けのPositiveプロンプト生成"""
        parts = ["masterpiece, best quality, high quality, highly detailed, extremely detailed, expressive"]

        if content:
            parts.append(content)
        if character:
            parts.append(f"(solo:1.1), (masterpiece composition centering on {character}:1.4), intricately detailed face, glowing eyes, perfect anatomy")
        if structure_hint:
            parts.append(structure_hint)
        if genre_hint:
            parts.append(genre_hint)
        if style_hint:
            parts.append(style_hint)

        return ", ".join(parts)

    def format_nb2_negative(self, base_negative: str = "", has_character_image: bool = False) -> str:
        """nanobanana2向けのNegativeプロンプト生成"""
        # nanobanana2向けの標準ネガティブ
        parts = ["worst quality, low quality, bad anatomy, missing fingers, bad hands, text, error, missing arms, missing legs, extra arms, extra legs, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"]
        if base_negative:
            parts.append(base_negative)
            
        if has_character_image:
            parts.append("original reference background, copied background, unrelated objects from reference")
            
        return ", ".join(parts)
