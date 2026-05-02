"""Visual Creative Studio - 基本動作テスト"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_state_schema():
    """SessionState の基本操作テスト"""
    from core.state_schema import SessionState

    # 作成
    state = SessionState()
    assert state.session_id
    assert state.mode == ""
    assert state.version == 1

    # 更新
    state.update({"mode": "design", "title": "テスト", "platform": "instagram"})
    assert state.mode == "design"
    assert state.title == "テスト"

    # JSON変換
    json_str = state.to_json()
    restored = SessionState.from_json(json_str)
    assert restored.mode == "design"
    assert restored.title == "テスト"

    # メッセージ追加
    state.add_message("user", "テストメッセージ")
    assert len(state.messages) == 1
    assert state.messages[0]["role"] == "user"

    print("[PASS] test_state_schema")


def test_intent_parser():
    """意図解析テスト"""
    from core.intent_parser import parse_intent

    # 新規作成 : Instagram
    result = parse_intent("Instagram用に図解カルーセルを作りたい。AI活用の基本を5枚で", {})
    assert result["intent"] == "new_creation", f"Expected new_creation, got {result['intent']}"
    assert result["mode"] == "design"
    assert result["detected_params"].get("platform") == "instagram"
    assert result["detected_params"].get("page_count") == 5

    # 新規作成 : 4コマ漫画
    result = parse_intent("4コマ漫画で、AIあるある", {})
    assert result["intent"] == "new_creation"
    assert result["mode"] == "four_panel_manga"

    # 修正指示
    result = parse_intent("もっと高級感を出して", {"mode": "design"})
    assert result["intent"] == "modification"
    assert result["detected_params"].get("style") == "luxury"

    # 修正指示 : N枚目
    result = parse_intent("2枚目だけ文字を減らして", {"mode": "design"})
    assert result["intent"] == "modification"
    assert result["modification_target"] == "slide_1"

    # 確認応答
    result = parse_intent("はい", {})
    assert result["intent"] == "confirmation"

    # 世界観統一
    result = parse_intent("世界観を統一して一式作って", {})
    assert result["intent"] == "new_creation"
    assert result["mode"] == "creative_suite"

    print("[PASS] test_intent_parser")


def test_conversation_engine():
    """会話エンジンテスト"""
    from core.state_schema import SessionState
    from core.conversation import ConversationEngine

    engine = ConversationEngine()
    state = SessionState()

    # 新規作成
    result = engine.process_input(state, "Instagram用に図解カルーセルを作りたい。AI活用の基本を5枚で")
    assert state.mode == "design"
    assert state.platform == "instagram"
    assert state.page_count == 5

    # タイトルが未設定なので質問が返る
    if not state.title:
        assert not result["should_generate"]

    # タイトルを提供
    result = engine.process_input(state, "AI活用の基本5ステップ")
    assert state.title == "AI活用の基本5ステップ"

    # 十分な情報が揃ったら生成
    assert result["should_generate"]

    print("[PASS] test_conversation_engine")


def test_design_generator():
    """デザイン生成テスト"""
    from core.state_schema import SessionState
    from generators.design_generator import DesignGenerator

    gen = DesignGenerator()
    state = SessionState()
    state.mode = "design"
    state.goal = "AI活用入門"
    state.title = "AI活用の基本"
    state.platform = "instagram"
    state.style = "simple"
    state.size = "instagram_portrait"
    state.page_count = 3

    results = gen.generate(state)
    assert len(results) == 3
    assert all(r["type"] == "svg" for r in results)
    assert all("<svg" in r["content"] for r in results)
    assert all(r["content"].count("</svg>") == 1 for r in results)

    print("[PASS] test_design_generator")


def test_manga_4panel_generator():
    """4コマ漫画生成テスト"""
    from core.state_schema import SessionState
    from generators.manga_4panel import Manga4PanelGenerator

    gen = Manga4PanelGenerator()
    state = SessionState()
    state.mode = "four_panel_manga"
    state.goal = "AIを使いたいけど最初の一歩が怖い"
    state.title = "AI初心者あるある"
    state.style = "pop"

    results = gen.generate(state)
    assert len(results) == 1
    assert "<svg" in results[0]["content"]
    assert len(state.panels) == 4

    print("[PASS] test_manga_4panel_generator")


def test_manga_1page_generator():
    """1ページ漫画生成テスト"""
    from core.state_schema import SessionState
    from generators.manga_1page import Manga1PageGenerator

    gen = Manga1PageGenerator()
    state = SessionState()
    state.mode = "one_page_manga"
    state.goal = "プログラミング初心者あるある"
    state.title = "プログラマーの日常"
    state.style = "simple"

    results = gen.generate(state)
    assert len(results) == 1
    assert "<svg" in results[0]["content"]
    assert len(state.panels) >= 4

    print("[PASS] test_manga_1page_generator")


def test_character_series_generator():
    """キャラクターシリーズ生成テスト"""
    from core.state_schema import SessionState
    from generators.character_series import CharacterSeriesGenerator

    gen = CharacterSeriesGenerator()
    state = SessionState()
    state.mode = "fixed_character_series"
    state.goal = "キャラクター展開"
    state.title = "アイちゃん"
    state.page_count = 3
    state.character_settings = {
        "enabled": True,
        "name": "アイちゃん",
        "appearance": "20代女性",
        "hair": "ピンクのツインテール",
        "outfit": "白い制服",
        "colors": ["#FF69B4", "#FFB6C1"],
        "personality": "明るくて好奇心旺盛",
        "expression_style": "",
        "pose_style": "",
        "reference_notes": "",
        "ng_items": [],
        "worldview_notes": "",
    }

    results = gen.generate(state)
    assert len(results) == 3
    assert all("<svg" in r["content"] for r in results)

    print("[PASS] test_character_series_generator")


def test_creative_suite_generator():
    """世界観統一セット生成テスト"""
    from core.state_schema import SessionState
    from generators.creative_suite import CreativeSuiteGenerator

    gen = CreativeSuiteGenerator()
    state = SessionState()
    state.mode = "creative_suite"
    state.goal = "AI活用入門"
    state.title = "AI入門"
    state.worldview = "テック系クール"
    state.style = "business"

    results = gen.generate(state)
    assert len(results) > 0
    assert all("<svg" in r["content"] for r in results)

    print("[PASS] test_creative_suite_generator")


def test_session_manager():
    """セッション管理テスト"""
    from core.state_schema import SessionState
    from core.session_manager import SessionManager

    mgr = SessionManager()

    # 作成・保存
    state = mgr.create_session()
    state.mode = "design"
    state.title = "テストセッション"
    mgr.save_session(state)

    # 読み込み
    loaded = mgr.load_session(state.session_id)
    assert loaded is not None
    assert loaded.title == "テストセッション"

    # 一覧
    sessions = mgr.list_sessions()
    assert any(s["session_id"] == state.session_id for s in sessions)

    # バージョン保存
    state.version = 1
    mgr.save_version(state)
    versions = mgr.get_version_history(state.session_id)
    assert len(versions) > 0

    # 削除
    mgr.delete_session(state.session_id)
    assert mgr.load_session(state.session_id) is None

    print("[PASS] test_session_manager")


def test_style_variations():
    """全スタイルの生成テスト"""
    from core.state_schema import SessionState
    from generators.design_generator import DesignGenerator

    gen = DesignGenerator()
    styles = ["simple", "pop", "luxury", "business", "friendly"]

    for style in styles:
        state = SessionState()
        state.mode = "design"
        state.goal = "テスト"
        state.title = "テスト"
        state.platform = "instagram"
        state.style = style
        state.size = "instagram_portrait"
        state.page_count = 1

        results = gen.generate(state)
        assert len(results) == 1
        assert "<svg" in results[0]["content"]

    print("[PASS] test_style_variations")


if __name__ == "__main__":
    test_state_schema()
    test_intent_parser()
    test_conversation_engine()
    test_design_generator()
    test_manga_4panel_generator()
    test_manga_1page_generator()
    test_character_series_generator()
    test_creative_suite_generator()
    test_session_manager()
    test_style_variations()
    print("\n[OK] All tests passed!")
