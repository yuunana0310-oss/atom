"""
霊視師 月詠 - 四柱推命 個人鑑定記事 生成スクリプト
=================================================
usage:
  python generate_meishiki.py 1990 11 1           # 1990年11月1日生まれの鑑定
  python generate_meishiki.py 1985 3 15 --weekly   # 鑑定 + 今週の運勢も付ける
"""

import os
import sys
import io
import argparse
from pathlib import Path
from datetime import datetime
import anthropic
from dotenv import load_dotenv
from shichusuimei import calculate_meishiki, format_meishiki, TSUHENSEI_MEANING, TENKAN_YOMI

# Windowsコンソール対応
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output" / "meishiki"


def build_system_prompt():
    return """あなたは霊視師 月詠（つきよみ）です。
東洋占術の最高峰である「四柱推命」と、人生の設計図を克明に描き出す「紫微斗数（しびとすう）」の両方を極めた、現代に現れた伝説の鑑定師として振る舞ってください。

【キャラクター設定】
- 名前：霊視師 月詠（れいしし つきよみ）
- 占術：四柱推命（エネルギーの波）と紫微斗数（人生の配役）を統合した「ハイブリッド霊視」
- 文体：です・ます調。詩的かつ断定的。読者の魂に語りかけるような、神秘的で重厚な口調
- 禁止事項：「AIが生成」「確率」「統計」「一般的に」などの言葉は絶対に使わない

【鑑定の心得】
- 四柱推命で「人生の大きな季節（運気の波）」を読み、紫微斗数で「人生の具体的な場面（12の宮）」を詳細に霊視する。
- 専門用語を自然に使いつつ、読者が「自分の人生の攻略本」を受け取ったと感じるような、圧倒的な情報量とリアリティを追求する。
- 4,000〜5,000字規模の、noteで高単価販売されるにふさわしい「特濃鑑定」を書き上げる。
"""


def build_reading_prompt(meishiki, include_weekly=False, include_romance=False):
    m = meishiki
    y = m["year_pillar"]
    mo = m["month_pillar"]
    d = m["day_pillar"]
    h = m.get("hour_pillar")
    n = m["nichikan"]
    gogyo = m["gogyo_balance"]
    
    # 現在の日付を取得
    curr_date = datetime.now().strftime("%Y年%m月%d日")
    curr_year = datetime.now().year

    prompt = f"""現在は {curr_date} です。
この日付を起点として、四柱推命と紫微斗数の叡智を融合させた「ハイブリッド霊視鑑定書」を書いてください。
読者が一生の指針にできるような、密度の濃い4,000字〜5,000字程度の鑑定を目指してください。

【対象】
生年月日: {m['birth_date']}

【四柱推命データ】
年柱: {y['label']}（通変星: {y['tsuhensei']}、十二運: {y['junishi_un']}）
月柱: {mo['label']}（通変星: {mo['tsuhensei']}、十二運: {mo['junishi_un']}）
日柱: {d['label']}（十二運: {d['junishi_un']}）
"""
    if h:
        prompt += f"時柱: {h['label']}（通変星: {h['tsuhensei']}、十二運: {h['junishi_un']}）\n"

    prompt += f"""
日干: {n['stem']} — {n['gogyo']}{n['inyo']}
格局: {m['kakkyoku']}
五行バランス: 木={gogyo['木']} 火={gogyo['火']} 土={gogyo['土']} 金={gogyo['金']} 水={gogyo['水']}

【記事構成】

# {m['birth_date']}生まれのあなたへ — 魂の深層と人生の設計図を解き明かす「月詠」特別鑑定書

## 1. 魂の起源と本質：四柱が語るあなたの原風景
日干「{n['stem']}」から読み解く魂の根源と使命。{n['character']}。
今世、なぜあなたはこの命式を選んで生まれてきたのか。その霊的背景を深掘りする。

## 2. 霊視의扉：これまでの歩みと言い当てられる真実
コールドリーディングを交え、過去から現在までの葛藤や成功を言い当てる。
月柱の通変星「{mo['tsuhensei']}（{TSUHENSEI_MEANING.get(mo['tsuhensei'], '')}）」から引き出される現実的な性格と、読者が心に秘めている「誰にも言えない思い」に共感する。

## 3. 【秘伝】人生の設計図：紫微斗数が描く12宮の真実
紫微斗数の視点からの詳細な霊視。
"""
    if include_romance:
        prompt += """
- **夫妻宮の深層霊視**: あなたの魂が求める真のパートナー像、運命の出会いの時期とサイン、そして過去生から続く愛の軌跡を徹底的に解き明かす。
- **命宮と福徳宮**: 愛され、愛するための精神的な土台と、恋愛における無意識のブロック。
- **遷移宮**: 新たな愛の出会いが訪れる場所と、その引き寄せ方。
"""
    else:
        prompt += """
- **命宮と福徳宮**: 精神性と、魂が求める本当の幸福。
- **官禄宮と財帛宮**: 仕事での成功の形と、財を成すための具体的なルート。
- **夫妻宮**: あなたを待ち受ける愛のドラマ、魂の伴侶の姿。
- **遷移宮、田宅宮など**: 外の世界での活躍、家庭環境や不動産の運。
"""

    prompt += """
## 4. エネルギーのバイオリズムと五行の調和
"""
    if h:
        prompt += f"- 晩年運（時柱: {h['tsuhensei']} / {h['junishi_un']}）が示す、人生の最終的な到達点と、次代への継承。\n"

    prompt += f"""
- 五行（木{gogyo['木']} 火{gogyo['火']} 土{gogyo['土']} 金{gogyo['金']} 水{gogyo['水']}）の偏りから導き出す、心身の健康と開運アクション。
"""
    
    if include_romance:
        prompt += f"""
## 5. 向こう三年の未来霊視：愛とご縁の軌跡（{curr_year}年〜{curr_year+2}年）
**【絶対厳守事項】必ず {curr_year}年、{curr_year+1}年、{curr_year+2}年の「3年分」をこの順番で、具体的な年号をタイトルにして詳しく解説してください。**
**過去（2024年や2025年など）の運勢は一切書かないでください。現在は{curr_year}年であることを忘れないでください。**
**未来予測の内容は「恋愛、出会い、結婚、パートナーシップの発展」に特化して霊視してください。**

- **{curr_year}年：【恋愛テーマをここに】**
- **{curr_year+1}年：【恋愛テーマをここに】**
- **{curr_year+2}年：【恋愛テーマをここに】**

## 6. 月詠より：あなたの愛を照らす光
鑑定の結び。この世界に唯一無二のエロスと愛を与えられた存在として、読者を祝福し激励する。
"""
    else:
        prompt += f"""
## 5. 向こう三年の未来霊視（{curr_year}年〜{curr_year+2}年）
**【絶対厳守事項】必ず {curr_year}年、{curr_year+1}年、{curr_year+2}年の「3年分」をこの順番で、具体的な年号をタイトルにして詳しく解説してください。**
**過去（2024年や2025年など）の運勢は一切書かないでください。現在は{curr_year}年であることを忘れないでください。**

- **{curr_year}年：【テーマをここに】**
- **{curr_year+1}年：【テーマをここに】**
- **{curr_year+2}年：【テーマをここに】**

## 6. 月詠より：あなたの今生を照らす光
鑑定の結び。この世界に唯一無二の存在として生まれたあなたへの、祈りと激励。
"""

    if include_weekly:
        prompt += """
## 【特別付録】今週の運勢と幸運の鍵
"""

    prompt += f"""
【執筆の心得】
- 現在（{curr_year}年）を起点とした正確な未来予測を行うこと。
- 全体で4,500字前後を目指し、各セクションを濃密に描写しつつ、最後まで確実に書ききること。
- 「四柱推命の構造（骨組み）」と「紫微斗数のストーリー（肉付け）」を融合させ、専門的かつ神秘的なトーンを維持すること。
- すべてMarkdown形式で出力すること。
"""
    return prompt


def generate_reading(meishiki, include_weekly=False, include_romance=False):
    """Claude APIで鑑定文を生成"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_system_prompt()
    user_prompt = build_reading_prompt(meishiki, include_weekly, include_romance)

    print("[生成中] 霊視師 月詠が命式を鑑定しています...")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return message.content[0].text


def save_reading(meishiki, content):
    """鑑定結果を保存"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 日付と時間を YYYYMMDD_HH 形式に整形（0埋め）
    # 例: 2000年1月1日 10時 -> 20000101_10
    import re
    nums = re.findall(r'\d+', meishiki["birth_date"])
    
    if len(nums) >= 3:
        formatted_date = f"{nums[0]}{nums[1].zfill(2)}{nums[2].zfill(2)}"
        if len(nums) >= 4:
            formatted_date += f"_{nums[3].zfill(2)}"
    else:
        formatted_date = meishiki["birth_date"].replace(" ", "_") # fallback
        
    filename = f"meishiki_{formatted_date}.md"
    filepath = OUTPUT_DIR / filename

    header = f"""---
生成日: {datetime.now().strftime('%Y-%m-%d %H:%M')}
生年月日: {meishiki['birth_date']}
日柱: {meishiki['day_pillar']['label']}
格局: {meishiki['kakkyoku']}
ペルソナ: 霊視師 月詠
---

"""
    filepath.write_text(header + content, encoding="utf-8")
    print(f"[OK] 保存完了: {filepath}")
    print(f"     文字数: {len(content):,}字")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="霊視師 月詠 - 四柱推命 個人鑑定")
    parser.add_argument("year", type=int, help="生まれた年（例: 1990）")
    parser.add_argument("month", type=int, help="生まれた月（例: 11）")
    parser.add_argument("day", type=int, help="生まれた日（例: 1）")
    parser.add_argument("hour", type=int, nargs='?', default=None, help="生まれた時間（0-23、不明なら省略可）")
    parser.add_argument("--weekly", action="store_true", help="今週の運勢も追加する")
    parser.add_argument("--romance", action="store_true", help="恋愛・パートナーシップに特化した鑑定にする")
    parser.add_argument("--calc-only", action="store_true", help="命式の計算結果のみ表示（API不使用）")
    args = parser.parse_args()

    print("=" * 60)
    print("[霊視師 月詠] 四柱推命 個人鑑定")
    print("=" * 60)
    print(f"[対象] {args.year}年{args.month}月{args.day}日 {f'{args.hour}時' if args.hour is not None else '時間不明'} 生まれ")
    print()

    # 命式を計算
    meishiki = calculate_meishiki(args.year, args.month, args.day, args.hour)
    print(format_meishiki(meishiki))
    print()

    if args.calc_only:
        print("[完了] 命式の計算結果を表示しました（API未使用）")
        return

    # 鑑定文を生成
    content = generate_reading(meishiki, args.weekly, args.romance)
    filepath = save_reading(meishiki, content)

    print()
    print(f"[記事] {filepath}")
    print("[note投稿手順]")
    print("  1. 上記ファイルを開く")
    print("  2. 内容をコピー")
    print("  3. note.com に貼り付けて投稿！")
    print("=" * 60)


if __name__ == "__main__":
    main()
