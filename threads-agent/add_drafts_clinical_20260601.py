#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-06-01 新コンセプト『臨床の見方を残す』7投稿を drafts に一括投入"""
import json
import uuid
import os
from datetime import datetime

os.chdir(os.path.dirname(__file__))

posts = [
    # 01 A共感（自主トレ）
    {
        "content": "退院前に、自主トレを3つ説明した。\n本人もうなずいて、できていた。\n\nなのに次の外来で「家ではやってなくて」と言われる。\n説明が悪かったわけじゃない。\nその場で消える形だっただけ。\n\n何度も説明してきたことほど、\n資料にしていない。\n\nあなたが一番よく説明してる内容、何ですか？",
        "supplement": "僕も長いこと「ちゃんと説明したのに」で止まってた。\n原因は熱量じゃなくて、家に持って帰れる形がなかったこと。口頭は、その場で一番強くて、次の日には一番弱い。",
        "pattern": "empathy", "theme": "現場の一瞬_消える知識", "post_type": "empathy", "affiliate": "",
    },
    # 02 A共感（後輩指導）
    {
        "content": "後輩に「あの患者さん、大丈夫そうです」と言われた。\n少しだけ不安になる。\n\n何が大丈夫なのか。\nどこを見て、そう判断したのか。\nそこを聞くと、本人もうまく言えない。\n\n悪いのは後輩じゃない。\n判断の流れを、見える形で渡せてないこっちの番。\n\n伝えたことは、その場で終わらせたくない。",
        "supplement": "「大丈夫そう」を責めても何も残らない。\n僕がやってよかったのは、自分がどの順番で何を見てるかを一回だけ言葉にして紙にしたこと。後輩が迷った時に戻れる場所ができた。",
        "pattern": "empathy", "theme": "現場の一瞬_後輩指導", "post_type": "empathy", "affiliate": "",
    },
    # 03 B信頼（家族指導）
    {
        "content": "家族に「何に気をつければいいですか」と聞かれる。\nここで言葉を選ぶ。\n\n注意点を全部言うと、家族は不安になる。\n言わなすぎると、家で何も判断できない。\n\nだから家族指導の資料に入れるのは、\n注意点だけじゃなく「迷った時の判断目安」。\n\n・これは様子を見ていい\n・これは連絡してほしい\n\nこの線引きがあるだけで、家族の不安はかなり減る。",
        "supplement": "家族って「危険なこと」より「判断できないこと」が一番こわい。\n注意点を増やすほど親切に見えて、実は判断を全部こっちに戻してることがある。線を引くのも医療職の仕事だと思ってる。",
        "pattern": "trust", "theme": "資料化の型_家族指導", "post_type": "trust", "affiliate": "",
    },
    # 04 B信頼（資料設計）
    {
        "content": "患者説明資料を作る時、\n最初に決めるのはデザインじゃない。\n\n誰が読むのか。\nいつ読むのか。\n読んだあと、何をしてほしいのか。\n\nここが決まらないまま作ると、\nきれいだけど使われない資料になる。\n\n患者向けなら、安心。\n家族向けなら、判断の目安。\n後輩向けなら、考え方の順番。\n\n同じ医療知識でも、届ける相手で形は変えていい。",
        "supplement": "昔の僕は、見栄えから入って毎回つまずいてた。\nレイアウトをいくらいじっても、「誰が読むか」が曖昧だと中身が決まらない。デザインは最後でいい。先に相手を決めると、入れる情報と削る情報が勝手に見えてくる。",
        "pattern": "trust", "theme": "資料化の型_患者説明", "post_type": "trust", "affiliate": "",
    },
    # 05 C教育（自主トレ資料）
    {
        "content": "自主トレ資料が「家で続かない」時、\nたいてい入れすぎてる。\n\n家で続く資料に入れるのは、この3つだけ。\n\n・動きは1〜2個に絞る\n・回数より「いつやるか」を書く（朝・寝る前など）\n・できたかを○で書ける欄を1つ\n\n注意点を全部足すより、\n1個を続けられる形にした方が、結果が変わる。\n\n渡す前に、自分でこの3つを確認してる。",
        "supplement": "情報を足すのは簡単で、削るのが一番むずかしい。\n「これも大事、あれも大事」で増やすほど、家では何も残らない。続ける人を増やしたいなら、覚えることを減らす設計から始めると効く。",
        "pattern": "education", "theme": "資料化の型_自主トレ", "post_type": "education", "affiliate": "",
    },
    # 06 D note導線
    {
        "content": "AIを、医療職の代わりに使うのは怖い。\nそこは僕も同じです。\n\nでも、現場で何度も説明してきたことを\n1枚の資料に整理するなら、AIはかなり使える。\n\n判断は、医療職がする。\nAIは、表現を整える。順番を作る。見返せる形にする。\n\nこの役割分担なら、AIは怖い道具じゃない。\n臨床の見方を残す道具になる。\n\nその最初の1枚を作る手順を、noteにまとめました。",
        "supplement": "誤解されがちなんですが、AIに「判断させる」話は一切してません。\n最後に確認するのは必ず医療職。AIがやるのは、頭の中にある説明を見返せる形に並べ替えるところまで。そこだけでも、現場はけっこう変わります。",
        "pattern": "note_funnel", "theme": "AIへの安心設計_note導線", "post_type": "note_funnel",
        "affiliate": "その手順、スクショ付きでnoteにまとめてます。AIが苦手でも進められる形にしたので、プロフィールから覗いてみてください。",
    },
    # 07 E販売
    {
        "content": "「自分の経験なんて、当たり前すぎる」\n医療職、だいたいこう言う。\n\nでも、あなたが何度も説明してきたことは、\n患者にとっても後輩にとっても、何度でも必要な内容です。\n\n当たり前すぎて、資料にしていないだけ。\n\n患者説明・家族指導・自主トレ・勉強会・後輩指導。\nこのどれかを、見返せる教材に変えるための手順を\nひとつのキットにまとめました。\n\nAIは補助。最後に確認するのは、あなた。\n医療職の知識を残すための入口です。",
        "supplement": "作ったきっかけは、僕自身が「説明してきたことが毎回その場で消える」のがもったいなかったから。\nGPTsの機能がすごい、という話ではなくて、医療職が当たり前にやってきたことを残す入口として使ってもらえたら、という温度で作りました。",
        "pattern": "sales", "theme": "note導線_スターターキット", "post_type": "sales",
        "affiliate": "キットの中身と、どんな資料が作れるかはnoteに書いてます。プロフィールのリンクから見られます。",
    },
]

scores_detail = {
    "hook_strength": 9, "usefulness": 8, "specificity": 9, "tempo": 9,
    "persona_match": 10, "originality": 9, "readability": 9,
    "emotional_resonance": 9, "call_to_action": 8, "platform_fit": 10,
    "conversation_potential": 9, "original_viewpoint": 9,
}

entries = []
for p in posts:
    entries.append({
        "id": str(uuid.uuid4()),
        "content": p["content"],
        "thread_replies": [p["supplement"]],
        "pattern": p["pattern"],
        "theme": p["theme"],
        "score": 9.0,
        "scores_detail": dict(scores_detail),
        "has_affiliate": bool(p["affiliate"]),
        "affiliate_comment": p["affiliate"],
        "post_type": p["post_type"],
        "created_at": datetime.now().isoformat(),
        "status": "draft",
    })

path = "data/drafts.json"
with open(path, "r", encoding="utf-8") as f:
    drafts = json.load(f)

# 新コンセプト投稿を先頭に（新しい順で表示されるよう逆順insert）
for e in reversed(entries):
    drafts.insert(0, e)

with open(path, "w", encoding="utf-8") as f:
    json.dump(drafts, f, ensure_ascii=False, indent=2)

print(f"[OK] {len(entries)}件を drafts に投入しました（合計 {len(drafts)}件）")
for e in entries:
    print(f"  - [{e['post_type']:>11}] {e['id'][:8]}  {e['content'].splitlines()[0]}")
