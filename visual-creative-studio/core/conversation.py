"""会話フロー制御"""
from core.state_schema import SessionState, STYLE_PRESETS, SIZE_PRESETS
from core.intent_parser import parse_intent


# モード別の必須/任意フィールド
MODE_REQUIRED_FIELDS = {
    "design": {
        "required": ["goal", "platform", "title"],
        "optional": ["subtitle", "body_text", "style", "size", "page_count", "cta", "tone"],
        "defaults": {"style": "simple", "size": "instagram_portrait", "page_count": 5}
    },
    "fixed_character_series": {
        "required": ["goal", "title"],
        "optional": ["page_count", "style", "platform"],
        "defaults": {"page_count": 3, "style": "pop"}
    },
    "four_panel_manga": {
        "required": ["goal", "title"],
        "optional": ["style", "tone", "genre"],
        "defaults": {"style": "pop", "page_count": 1, "size": "manga_4panel"}
    },
    "one_page_manga": {
        "required": ["goal", "title"],
        "optional": ["style", "tone", "genre", "page_count"],
        "defaults": {"style": "simple", "page_count": 1, "size": "manga_1page"}
    },
    "creative_suite": {
        "required": ["goal", "worldview"],
        "optional": ["style", "tone", "genre"],
        "defaults": {"style": "simple"}
    }
}

# フィールドの日本語ラベル
FIELD_LABELS = {
    "goal": "制作の目的",
    "platform": "プラットフォーム",
    "title": "タイトル",
    "subtitle": "サブタイトル",
    "body_text": "本文テキスト",
    "style": "デザインスタイル",
    "size": "サイズ",
    "page_count": "枚数",
    "cta": "CTA（行動喚起テキスト）",
    "tone": "トーン・雰囲気",
    "worldview": "世界観",
    "genre": "ジャンル",
}

# モードの日本語ラベル
MODE_LABELS = {
    "design": "デザイン生成",
    "fixed_character_series": "固定キャラクター複数枚",
    "four_panel_manga": "4コマ漫画",
    "one_page_manga": "1ページ漫画",
    "creative_suite": "世界観統一セット"
}


class ConversationEngine:
    """会話フロー制御エンジン"""

    def process_input(self, state: SessionState, user_text: str) -> dict:
        """
        ユーザー入力を処理して応答を生成する

        Returns:
            {
                "response": str,           # AI応答テキスト
                "should_generate": bool,   # 生成を実行するか
                "state_updates": dict,     # 状態更新
                "mode": str               # 現在のモード
            }
        """
        # 意図解析
        intent_result = parse_intent(user_text, state.to_dict())
        intent = intent_result["intent"]
        detected_mode = intent_result["mode"]
        detected_params = intent_result["detected_params"]

        # メッセージ記録
        state.add_message("user", user_text)

        result = {
            "response": "",
            "should_generate": False,
            "state_updates": {},
            "mode": state.mode
        }

        # pending_questionsがある場合は、回答として優先処理
        if state.pending_questions and intent != "modification":
            return self._handle_info_provide(state, user_text, detected_params, result)

        if intent == "confirmation":
            return self._handle_confirmation(state, result)
        elif intent == "modification":
            return self._handle_modification(state, user_text, intent_result, result)
        elif intent == "new_creation":
            return self._handle_new_creation(state, user_text, detected_mode, detected_params, result)
        else:  # info_provide
            return self._handle_info_provide(state, user_text, detected_params, result)

    def _handle_confirmation(self, state: SessionState, result: dict) -> dict:
        """確認応答を処理"""
        # 十分な情報があれば生成
        if self._has_enough_info(state):
            result["should_generate"] = True
            result["response"] = self._generate_start_message(state)
        else:
            # まだ足りない情報を聞く
            missing = self._get_missing_fields(state)
            result["response"] = self._ask_next_question(state, missing)
        return result

    def _handle_modification(self, state: SessionState, user_text: str,
                             intent_result: dict, result: dict) -> dict:
        """修正指示を処理"""
        mod_params = intent_result.get("detected_params", {})
        mod_target = intent_result.get("modification_target", "all")

        # 変更リクエストを記録
        state.change_requests.append({
            "text": user_text,
            "target": mod_target,
            "params": mod_params
        })

        # スタイル変更
        if "style" in mod_params:
            state.style = mod_params["style"]
            result["state_updates"]["style"] = mod_params["style"]
            # スタイル変更時はスライドを再生成（色が変わるため）
            state.slides = []

        # 色変更
        if "color_override" in mod_params:
            state.accent_color = mod_params["color_override"]
            result["state_updates"]["accent_color"] = mod_params["color_override"]

        # バージョンアップ
        state.version += 1
        result["should_generate"] = True
        result["response"] = f"了解しました！「{user_text}」の修正を反映します。\n（v{state.version} を生成中...）"
        result["mode"] = state.mode
        return result

    def _handle_new_creation(self, state: SessionState, user_text: str,
                             detected_mode: str, detected_params: dict, result: dict) -> dict:
        """新規作成を処理"""
        # モード設定
        if detected_mode:
            state.mode = detected_mode
            result["mode"] = detected_mode
            result["state_updates"]["mode"] = detected_mode

        # 検出されたパラメータを適用
        for key, value in detected_params.items():
            if hasattr(state, key):
                setattr(state, key, value)
                result["state_updates"][key] = value

        # goalが未設定なら入力テキストをgoalとして使う
        if not state.goal:
            state.goal = user_text
            result["state_updates"]["goal"] = user_text

        # 漫画/キャラモードはgoalからtitleを自動生成
        if not state.title and state.goal:
            if state.mode in ("four_panel_manga", "one_page_manga", "fixed_character_series"):
                # goalの先頭30文字をタイトルとして使う
                state.title = state.goal[:30]
                result["state_updates"]["title"] = state.title

        # デフォルト値の適用
        self._apply_defaults(state)

        # 十分な情報があるか確認
        if self._has_enough_info(state):
            result["should_generate"] = True
            result["response"] = self._generate_start_message(state)
        else:
            missing = self._get_missing_fields(state)
            mode_label = MODE_LABELS.get(state.mode, state.mode)
            result["response"] = f"📐 **{mode_label}**モードですね！\n\n"
            result["response"] += self._summarize_current_state(state)
            result["response"] += "\n\n" + self._ask_next_question(state, missing)

        return result

    def _handle_info_provide(self, state: SessionState, user_text: str,
                             detected_params: dict, result: dict) -> dict:
        """情報提供を処理"""
        # パラメータを適用
        for key, value in detected_params.items():
            if hasattr(state, key):
                setattr(state, key, value)
                result["state_updates"][key] = value

        # pending_questionsに回答を適用
        if state.pending_questions:
            current_q = state.pending_questions[0]
            field_name = current_q.get("field", "")
            if field_name and hasattr(state, field_name):
                setattr(state, field_name, user_text)
                result["state_updates"][field_name] = user_text
            state.pending_questions.pop(0)

        # 十分なら生成
        if self._has_enough_info(state):
            result["should_generate"] = True
            result["response"] = self._generate_start_message(state)
        else:
            missing = self._get_missing_fields(state)
            result["response"] = "ありがとうございます！\n\n"
            result["response"] += self._summarize_current_state(state)
            result["response"] += "\n\n" + self._ask_next_question(state, missing)

        result["mode"] = state.mode
        return result

    def _has_enough_info(self, state: SessionState) -> bool:
        """生成に十分な情報があるか"""
        if not state.mode:
            return False
        config = MODE_REQUIRED_FIELDS.get(state.mode, {})
        required = config.get("required", [])
        for field in required:
            value = getattr(state, field, "")
            if not value:
                return False
        return True

    def _get_missing_fields(self, state: SessionState) -> list:
        """不足フィールドを返す"""
        if not state.mode:
            return ["mode"]
        config = MODE_REQUIRED_FIELDS.get(state.mode, {})
        required = config.get("required", [])
        missing = []
        for field in required:
            value = getattr(state, field, "")
            if not value:
                missing.append(field)
        return missing

    def _apply_defaults(self, state: SessionState):
        """デフォルト値を適用"""
        if not state.mode:
            return
        config = MODE_REQUIRED_FIELDS.get(state.mode, {})
        defaults = config.get("defaults", {})
        for key, value in defaults.items():
            current = getattr(state, key, "")
            if not current:
                setattr(state, key, value)

    def _ask_next_question(self, state: SessionState, missing: list) -> str:
        """次の質問を生成"""
        if not missing:
            return "情報は十分です！「生成して」と言っていただければ作成を開始します 🎨"

        field = missing[0]
        label = FIELD_LABELS.get(field, field)

        # フィールドごとに自然な質問文
        questions = {
            "mode": "どんなものを作りましょうか？\n\n"
                    "💡 選択肢:\n"
                    "- Instagram / YouTube / note 向けデザイン\n"
                    "- 4コマ漫画\n"
                    "- 1ページ漫画\n"
                    "- 固定キャラクターの複数展開\n"
                    "- 世界観統一のクリエイティブ一式",
            "goal": "どんな目的で使う制作物ですか？\n（例: 「AI活用の基本を図解で伝えたい」「サービスの魅力を紹介したい」）",
            "platform": "どのプラットフォーム向けですか？\n（Instagram / YouTube / note / Threads / その他）",
            "title": "タイトルは何にしますか？\n（例: 「AI活用の基本5ステップ」「Claude Code入門」）",
            "subtitle": "サブタイトルがあれば教えてください。（なしでもOK）",
            "worldview": "世界観やトーンについて教えてください。\n（例: 「テックっぽくクール」「温かみのある手書き風」）",
            "style": "デザインスタイルを選んでください:\n"
                     "- **シンプル**: 洗練されたミニマル\n"
                     "- **ポップ**: 明るく楽しい\n"
                     "- **高級感**: 重厚で上品\n"
                     "- **ビジネス**: 信頼感のある\n"
                     "- **親しみやすい**: 温かみのある",
        }

        question = questions.get(field, f"**{label}**を教えてください。")

        # pending_questionsに記録
        state.pending_questions = [{"field": field, "label": label}]

        return question

    def _summarize_current_state(self, state: SessionState) -> str:
        """現在決まっている情報をまとめる"""
        parts = []
        if state.mode:
            parts.append(f"📌 モード: **{MODE_LABELS.get(state.mode, state.mode)}**")
        if state.platform:
            parts.append(f"📱 プラットフォーム: **{state.platform}**")
        if state.goal:
            goal_short = state.goal[:50] + "..." if len(state.goal) > 50 else state.goal
            parts.append(f"🎯 目的: {goal_short}")
        if state.title:
            parts.append(f"📝 タイトル: {state.title}")
        if state.style:
            style_label = STYLE_PRESETS.get(state.style, {}).get("label", state.style)
            parts.append(f"🎨 スタイル: {style_label}")
        if state.page_count > 1:
            parts.append(f"📄 枚数: {state.page_count}枚")

        if parts:
            return "**現在の設定:**\n" + "\n".join(parts)
        return ""

    def _generate_start_message(self, state: SessionState) -> str:
        """生成開始メッセージ"""
        mode_label = MODE_LABELS.get(state.mode, state.mode)
        msg = f"✨ 準備完了！ **{mode_label}** を生成します。\n\n"
        msg += self._summarize_current_state(state)
        msg += "\n\n⏳ 生成中..."
        return msg
