#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import uuid
from datetime import datetime
import os

os.chdir(os.path.dirname(__file__))

# 新規投稿エントリを作成
new_post = {
    "id": str(uuid.uuid4()),
    "content": """患者さんが自宅リハを続けない理由、わかりますか？

院内では頑張るのに、家に帰るとぱったり止める。このギャップ、全リハビリ職が直面する「あるある」です。

その正体は、患者さんが「これは自分の身体の問題」と腹落ちしていないから。つまり、他人事のままなんです。

そこで僕が意識している3つのアプローチ：

ステップ1：「なぜ」を患者さんに言語化させる
「膝が痛くなる理由、あなたの身体で何が起きていると思いますか？」と聞く。患者さんが説明した瞬間、リハビリが「医者の指示」から「自分の身体との対話」に変わります。

ステップ2：1ヶ月後の目標より、1週間後の小さな成功を重ねる
大きなゴールは遠すぎて続かない。だから「来週、階段を5段多く上れたら成功」みたいな小さな勝利を何度も味わわせる。その繰り返しが習慣化につながります。

ステップ3：プログラムの調整権を患者さんに渡す
「このメニューが正解」と押し付けるのではなく、「自分の身体がどう反応するか試してみて、きつかったら教えてね」と。患者さんが主体になった瞬間、モチベーションが全然違う。

医学的根拠もある方法ですが、何より臨床で結果が出ます。

あなたの現場では、どのステップが一番難しい？
コメント欄で聞かせてください。同じ悩みを持つ職種の工夫もここで共有したいです。

このアカウントをフォローして、明日から使える臨床の工夫を毎日受け取りませんか？""",
    "pattern": "step_guide",
    "theme": "臨床実践",
    "score": 9.0,
    "scores_detail": {
        "hook_strength": 9,
        "usefulness": 9,
        "specificity": 9,
        "tempo": 9,
        "persona_match": 9,
        "originality": 8,
        "readability": 9,
        "emotional_resonance": 9,
        "call_to_action": 9,
        "platform_fit": 9
    },
    "has_affiliate": False,
    "affiliate_comment": "",
    "post_type": "step_guide",
    "created_at": datetime.now().isoformat(),
    "status": "draft"
}

try:
    with open("data/drafts.json", "r", encoding="utf-8") as f:
        drafts = json.load(f)

    drafts.insert(0, new_post)

    with open("data/drafts.json", "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)

    print("[OK] 投稿を drafts に登録しました")
    print(f"[ID] {new_post['id']}")
    print(f"[Score] {new_post['score']}")
    print(f"[Created] {new_post['created_at']}")
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
