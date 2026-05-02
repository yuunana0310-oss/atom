"""
pain_intake プロンプト定義

現状: ルールベース実装
将来: [FUTURE_LLM] マークの箇所をClaude APIに置き換える

LLM化の際の差し替えポイント:
1. extract_pain_candidates()     → Claude に判定させる
2. summarize_pain()              → Claude に要約させる
3. score_severity/urgency()      → Claude に採点させる
4. detect_audience_type()        → Claude に分類させる
5. extract_situation()           → Claude に抽出させる
6. extract_failed_attempts()     → Claude に抽出させる
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# [FUTURE_LLM] 悩み抽出プロンプト
# ---------------------------------------------------------------------------

EXTRACT_PAIN_SYSTEM = """\
あなたは読者インサイト分析の専門家です。
与えられたテキストから「読者が感じている困りごと・悩み・失敗体験」を抽出してください。

## 抽出する内容
- 具体的な困りごと（「〇〇ができない」「〇〇で詰まった」など）
- 失敗体験（「〇〇を試したが上手くいかなかった」など）
- 不安・恐れ（「〇〇が怖い」「〇〇が心配」など）

## 除外する内容
- 純粋な感想・賞賛（「すごい」「面白い」「楽しい」など）
- 事実の陳述のみで悩みが含まれないもの

出力はJSON形式で返してください。
"""

EXTRACT_PAIN_USER = """\
以下のテキストから悩みポイントを抽出してください:

{text}

出力形式:
{{
  "has_pain": true/false,
  "pain_summary": "悩みの要約（100字以内）",
  "severity": 1-5,
  "urgency": 1-5,
  "audience_type": "想定読者属性",
  "situation": "悩みが発生した状況",
  "failed_attempts": ["試したが失敗したこと1", ...],
  "related_tags": ["タグ1", ...]
}}
"""


# ---------------------------------------------------------------------------
# [FUTURE_LLM] 類似判定プロンプト
# ---------------------------------------------------------------------------

SIMILARITY_SYSTEM = """\
2つの悩みポイントが「同じ本質的な悩みを表しているか」を判定してください。
同じ本質的な悩みとは、解決策が共通になる可能性が高いものです。
"""

SIMILARITY_USER = """\
悩みA: {pain_a}
悩みB: {pain_b}

判定結果をJSONで返してください:
{{
  "is_similar": true/false,
  "similarity_score": 0.0-1.0,
  "reason": "判定理由"
}}
"""
