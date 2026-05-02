"""ユーザー意図解析 (ルールベース)"""
import re
from typing import Tuple


# 意図判定キーワード
MODE_KEYWORDS = {
    "design": [
        "カルーセル", "サムネ", "サムネイル", "thumbnail", "youtube", "ユーチューブ",
        "instagram", "インスタ", "note", "ノート", "図解", "スライド",
        "サービス紹介", "説明", "ビジュアル", "バナー", "OGP", "記事"
    ],
    "fixed_character_series": [
        "キャラ", "キャラクター", "固定キャラ", "このキャラ", "character",
        "複数枚", "展開", "シリーズ"
    ],
    "four_panel_manga": [
        "4コマ", "四コマ", "4こま", "よんこま", "4-panel", "4panel"
    ],
    "one_page_manga": [
        "1ページ漫画", "漫画", "マンガ", "ネーム", "コマ割り", "manga",
        "1ページ", "一ページ"
    ],
    "creative_suite": [
        "一式", "セット", "統一", "世界観", "まとめて", "全部",
        "suite", "パッケージ"
    ]
}

# 修正指示キーワード
MODIFICATION_KEYWORDS = [
    "もっと", "変えて", "変更", "修正", "直して", "差し替え",
    "だけ", "のみ", "背景", "色を", "フォント", "文字",
    "大きく", "小さく", "明るく", "暗く", "太く", "細く",
    "増やし", "減らし", "追加", "削除", "消して", "入れて",
    "高級感", "カジュアル", "シンプル", "派手", "落ち着い",
    "枚目", "コマ目", "ページ"
]

# 確認応答キーワード
CONFIRMATION_KEYWORDS = [
    "はい", "yes", "うん", "それで", "お願い", "OK", "ok", "おk",
    "いいね", "いいよ", "進めて", "作って", "生成して", "決定",
    "そのまま", "了解", "りょうかい"
]

# プラットフォーム検出
PLATFORM_KEYWORDS = {
    "instagram": ["instagram", "インスタ", "insta", "ig"],
    "youtube": ["youtube", "ユーチューブ", "yt"],
    "note": ["note", "ノート"],
    "twitter": ["twitter", "ツイッター", "x"],
    "threads": ["threads", "スレッズ"],
}

# スタイル検出
STYLE_KEYWORDS = {
    "simple": ["シンプル", "simple", "ミニマル", "すっきり", "きれい"],
    "pop": ["ポップ", "pop", "かわいい", "明るい", "楽しい", "カラフル"],
    "luxury": ["高級", "luxury", "プレミアム", "上品", "重厚", "ラグジュアリー", "リッチ"],
    "business": ["ビジネス", "business", "プロ", "信頼", "堅い", "フォーマル"],
    "friendly": ["親しみ", "friendly", "やさしい", "温かい", "カジュアル", "フレンドリー"],
}


def parse_intent(text: str, current_state: dict) -> dict:
    """
    ユーザー入力の意図を解析する

    Returns:
        {
            "intent": "new_creation" | "modification" | "confirmation" | "info_provide",
            "mode": str or None,
            "detected_params": dict,
            "modification_target": str or None,
            "raw_text": str
        }
    """
    text_lower = text.lower().strip()
    result = {
        "intent": "info_provide",
        "mode": None,
        "detected_params": {},
        "modification_target": None,
        "raw_text": text
    }

    # 1. 修正指示チェック（既にモードが確定しているセッションのみ）
    if current_state.get("mode") and _is_modification(text_lower):
        result["intent"] = "modification"
        result["modification_target"] = _detect_modification_target(text_lower)
        result["detected_params"] = _extract_modification_params(text, text_lower)
        return result

    # 2. モード検出（確認応答より優先）
    detected_mode = _detect_mode(text_lower)
    if detected_mode:
        result["intent"] = "new_creation"
        result["mode"] = detected_mode
        result["detected_params"] = _extract_params(text, text_lower)
        return result

    # 3. 確認応答チェック（モード検出されなかった場合のみ）
    if _is_confirmation(text_lower):
        result["intent"] = "confirmation"
        return result

    # 4. モードが既にセッションに設定されている場合
    if current_state.get("mode"):
        result["mode"] = current_state["mode"]
        result["intent"] = "info_provide"

    # 5. 新しい内容を含んでいるなら新規作成
    if not result["mode"] and not current_state.get("mode"):
        result["intent"] = "new_creation"
        result["mode"] = "design"

    # 6. パラメータ抽出
    result["detected_params"] = _extract_params(text, text_lower)

    return result


def _is_confirmation(text: str) -> bool:
    """確認応答かどうか"""
    for kw in CONFIRMATION_KEYWORDS:
        if kw in text:
            return True
    # 短い入力は確認応答の可能性高い
    if len(text) < 5 and not any(c.isdigit() for c in text):
        return True
    return False


def _is_modification(text: str) -> bool:
    """修正指示かどうか"""
    count = sum(1 for kw in MODIFICATION_KEYWORDS if kw in text)
    return count >= 1


def _detect_mode(text: str) -> str:
    """モードを検出"""
    scores = {}
    for mode, keywords in MODE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[mode] = score

    if not scores:
        return ""

    # 4コマが明示的なら最優先
    if "four_panel_manga" in scores:
        return "four_panel_manga"

    # 世界観/一式が明示的なら
    if "creative_suite" in scores and scores["creative_suite"] >= 2:
        return "creative_suite"

    return max(scores, key=scores.get)


def _detect_modification_target(text: str) -> str:
    """修正対象を特定"""
    # 「N枚目」「Nコマ目」パターン
    match = re.search(r"(\d+)\s*枚目", text)
    if match:
        return f"slide_{int(match.group(1)) - 1}"

    match = re.search(r"(\d+)\s*コマ目", text)
    if match:
        return f"panel_{int(match.group(1)) - 1}"

    # 背景・色・文字などの部分指定
    if "背景" in text:
        return "background"
    if "色" in text:
        return "color"
    if "文字" in text or "テキスト" in text or "フォント" in text:
        return "text"
    if "タイトル" in text:
        return "title"
    if "キャラ" in text:
        return "character"

    return "all"


def _extract_modification_params(text: str, text_lower: str) -> dict:
    """修正パラメータを抽出"""
    params = {}

    # スタイル変更
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            params["style"] = style
            break

    # 色指定
    color_match = re.search(r"(#[0-9a-fA-F]{6})", text)
    if color_match:
        params["color_override"] = color_match.group(1)

    # テキスト変更
    if "文字を減らし" in text or "テキストを減らし" in text:
        params["text_action"] = "reduce"
    elif "文字を増やし" in text or "テキストを増やし" in text:
        params["text_action"] = "increase"

    # 溜め
    if "溜め" in text or "ため" in text:
        params["panel_emphasis"] = "dramatic_pause"

    return params


def _extract_params(text: str, text_lower: str) -> dict:
    """汎用パラメータ抽出"""
    params = {}

    # プラットフォーム
    for platform, keywords in PLATFORM_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            params["platform"] = platform
            break

    # スタイル
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            params["style"] = style
            break

    # ページ/枚数
    match = re.search(r"(\d+)\s*枚", text)
    if match:
        params["page_count"] = int(match.group(1))

    match = re.search(r"(\d+)\s*ページ", text)
    if match:
        params["page_count"] = int(match.group(1))

    # タイトルっぽい文字列（「」で囲まれたもの）
    title_match = re.search(r"[「『](.+?)[」』]", text)
    if title_match:
        params["title"] = title_match.group(1)

    # 用途キーワードから目的を推測
    if "図解" in text:
        params["goal"] = "図解コンテンツ"
        if "platform" not in params:
            params["platform"] = "instagram"
    if "入門" in text or "初心者" in text:
        params["tone"] = "初心者向け"
    if "あるある" in text:
        params["genre"] = "あるある"

    # サイズ推定 (プラットフォームから)
    if params.get("platform") == "instagram":
        params["size"] = "instagram_portrait"
    elif params.get("platform") == "youtube":
        params["size"] = "youtube_thumbnail"
    elif params.get("platform") == "note":
        params["size"] = "note_thumbnail"

    return params
