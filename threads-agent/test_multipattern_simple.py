#!/usr/bin/env python3
"""
Test: MultiPattern Generation Implementation
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.writer import WriterAgent
import config as config_module

def test():
    print("=" * 80)
    print("TEST: MultiPattern Generation with Prompt Caching")
    print("=" * 80)

    threads_dir = Path(__file__).parent
    knowledge_dir = threads_dir / "knowledge" / "account1"
    data_dir = threads_dir / "data" / "account1"

    # Load profile
    print("\n[1] Loading profile...")
    with open(knowledge_dir / "account_profile.json", encoding="utf-8") as f:
        profile = json.load(f)
    with open(data_dir / "feedback_instructions.json", encoding="utf-8") as f:
        feedback = json.load(f)
    print(f"  OK: {profile.get('account_name')}")

    # Load research + pattern
    print("\n[2] Loading research and pattern...")
    with open(data_dir / "research_cache.json", encoding="utf-8") as f:
        research = json.load(f)[0]
    with open(knowledge_dir / "post_patterns.json", encoding="utf-8") as f:
        patterns_data = json.load(f)
        patterns = patterns_data.get("patterns", [])
    pattern = patterns[0] if patterns else {"id": "test", "name": "test"}
    print(f"  OK: theme={research.get('theme')}, pattern={pattern.get('name')}")

    # Init WriterAgent
    print("\n[3] Initializing WriterAgent...")
    writer = WriterAgent(config=config_module, knowledge_dir=knowledge_dir, data_dir=data_dir)
    print(f"  OK: {writer.model}")

    # Test _build_prompt_fixed
    print("\n[4] Testing _build_prompt_fixed()...")
    try:
        fixed = writer._build_prompt_fixed(profile, feedback)
        print(f"  OK: {len(fixed)} chars")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test _build_prompt_variable
    print("\n[5] Testing _build_prompt_variable()...")
    try:
        variable = writer._build_prompt_variable(research, pattern, feedback)
        print(f"  OK: {len(variable)} chars")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test _generate_with_claude
    print("\n[6] Testing _generate_with_claude() [Calling API]...")
    try:
        response = writer._generate_with_claude(fixed, variable)
        if response:
            print(f"  OK: {len(response)} chars received")
        else:
            print(f"  WARN: API returned None (check API key)")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test _parse_claude_response_array
    print("\n[7] Testing _parse_claude_response_array()...")
    try:
        candidates = writer._parse_claude_response_array(response)
        if candidates:
            print(f"  OK: Parsed {len(candidates)} candidates")
        else:
            print(f"  ERROR: Failed to parse")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Test _select_best_candidate
    print("\n[8] Testing _select_best_candidate()...")
    try:
        ng_words = profile.get("ng_words", [])
        recent_texts = []
        history_path = data_dir / "post_history.json"
        if history_path.exists():
            with open(history_path, encoding="utf-8") as f:
                history = json.load(f)
                recent_texts = [p.get("content", "") for p in history[-100:]]

        best = writer._select_best_candidate(candidates, pattern, ng_words, recent_texts)
        if best:
            scores = best.get("scores", {})
            avg = sum(scores.values()) / len(scores) if scores else 0
            print(f"  OK: Selected best (avg_score={avg:.2f})")
        else:
            print(f"  WARN: All candidates rejected (may be OK)")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("SUCCESS: All tests passed!")
    print("=" * 80)
    print("\nNext step: Modify run() loop to integrate multipattern generation")
    return True

if __name__ == "__main__":
    success = test()
    sys.exit(0 if success else 1)
