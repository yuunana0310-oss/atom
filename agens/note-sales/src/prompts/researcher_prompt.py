"""
researcher プロンプト定義

現状: ルールベース実装
将来: [FUTURE_LLM] マークの箇所を Claude API に置き換える

LLM化の際の差し替えポイント:
1. generate_candidates_from_pains()   → Claude で候補生成
2. score_candidate_with_llm()         → Claude でスコアリング
3. deduplicate_with_llm()             → Claude で類似判定
4. generate_hook()                    → Claude でフック文生成
5. generate_why_now()                 → Claude で時事性コメント生成
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# [FUTURE_LLM] 候補生成プロンプト
# ---------------------------------------------------------------------------

GENERATE_CANDIDATES_SYSTEM = """\
あなたはnote記事のコンテンツストラテジストです。
読者の悩みデータをもとに、「売れるnote記事」の候補を生成してください。

## 生成ルール
- 3〜5件の候補を生成する
- 各候補は distinct なターゲット読者に向けること
- タイトルは note.com で売れるパターンに合わせる
- 有料設定できる根拠を必ず含める
- 煽り表現・誇大表現は避ける

## 売れるタイトルパターン
- 【ブラケット】 + 説明型
- 体験談（期間 + ツール + 正直な感想）
- ステップバイステップ（対象読者 + ゴール）
- 数字 + リスト型
"""

GENERATE_CANDIDATES_USER = """\
以下の読者の悩みデータをもとに、note記事候補を {count} 件生成してください。

## 悩みデータ
{pain_summaries}

## 出力形式（JSON配列）
[
  {{
    "topic_title": "記事タイトル",
    "hook": "冒頭フック文（読者への問いかけ）",
    "angle": "体験談/ガイド/比較/収益公開 のいずれか",
    "why_now": "今このテーマを書く理由",
    "expected_buyer_intent": "購読者が買う動機",
    "paid_reason": "有料にする根拠",
    "recommended_price_range": "300-980円",
    "audience_type": "ターゲット読者属性"
  }},
  ...
]
"""


# ---------------------------------------------------------------------------
# [FUTURE_LLM] スコアリングプロンプト
# ---------------------------------------------------------------------------

SCORING_SYSTEM = """\
与えられたnote記事候補を、以下の観点でスコアリングしてください（各0〜10点）。
- demand_score: 読者の需要の強さ
- monetization_score: 有料で売れる可能性
- threads_fit_score: Threads投稿への親和性（フック・訴求力）
- expertise_fit_score: 執筆者の専門性との一致度
- trend_score: 現在のトレンドとの一致度
"""

SCORING_USER = """\
記事候補:
タイトル: {title}
フック: {hook}
アングル: {angle}
対象悩み: {pain_summary}

スコアをJSONで返してください:
{{
  "demand_score": 0-10,
  "monetization_score": 0-10,
  "threads_fit_score": 0-10,
  "expertise_fit_score": 0-10,
  "trend_score": 0-10,
  "reasoning": "採点理由"
}}
"""
