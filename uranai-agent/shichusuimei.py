"""
四柱推命（三柱版）計算エンジン
=================================================
生年月日から年柱・月柱・日柱を算出し、
通変星・十二運・五行バランスを導き出す。

usage:
  from shichusuimei import calculate_meishiki
  result = calculate_meishiki(1990, 11, 1)
"""

from datetime import date

# ============================================================
# 基礎データ
# ============================================================

# 天干（てんかん）
TENKAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 地支（ちし）
CHISHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 天干の読み
TENKAN_YOMI = {
    "甲": "きのえ", "乙": "きのと", "丙": "ひのえ", "丁": "ひのと", "戊": "つちのえ",
    "己": "つちのと", "庚": "かのえ", "辛": "かのと", "壬": "みずのえ", "癸": "みずのと"
}

# 地支の読み
CHISHI_YOMI = {
    "子": "ね", "丑": "うし", "寅": "とら", "卯": "う", "辰": "たつ", "巳": "み",
    "午": "うま", "未": "ひつじ", "申": "さる", "酉": "とり", "戌": "いぬ", "亥": "い"
}

# 天干の五行
TENKAN_GOGYO = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
}

# 天干の陰陽
TENKAN_INYO = {
    "甲": "陽", "乙": "陰", "丙": "陽", "丁": "陰", "戊": "陽",
    "己": "陰", "庚": "陽", "辛": "陰", "壬": "陽", "癸": "陰"
}

# 地支の五行
CHISHI_GOGYO = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"
}

# 五行の相生・相剋
GOGYO_ORDER = ["木", "火", "土", "金", "水"]

# 通変星の算出テーブル
# key = (日干の五行インデックスからの差, 陰陽が同じか)
TSUHENSEI = {
    (0, True):  "比肩",    # 同じ五行・同じ陰陽
    (0, False): "劫財",    # 同じ五行・違う陰陽
    (1, True):  "食神",    # 日干が生じる・同じ陰陽
    (1, False): "傷官",    # 日干が生じる・違う陰陽
    (2, True):  "偏財",    # 日干が剋す・同じ陰陽
    (2, False): "正財",    # 日干が剋す・違う陰陽
    (3, True):  "偏官",    # 日干を剋す・同じ陰陽
    (3, False): "正官",    # 日干を剋す・違う陰陽
    (4, True):  "偏印",    # 日干を生じる・同じ陰陽
    (4, False): "印綬",    # 日干を生じる・違う陰陽
}

# 十二運
JUNISHI_UN = ["長生", "沐浴", "冠帯", "建禄", "帝旺", "衰", "病", "死", "墓", "絶", "胎", "養"]

# 日干から十二運の起点（地支インデックス）
JUNISHI_START = {
    "甲": 11, "乙": 6, "丙": 2, "丁": 9, "戊": 2,
    "己": 9, "庚": 5, "辛": 0, "壬": 8, "癸": 3
}

# 通変星の意味
TSUHENSEI_MEANING = {
    "比肩": "自立心・マイペース・独立志向。自分の力で道を切り開く",
    "劫財": "社交性・競争心・野心。仲間と切磋琢磨して伸びる",
    "食神": "楽観的・おおらか・才能豊か。自然体で周囲を和ませる",
    "傷官": "感受性・完璧主義・表現力。芸術的センスと鋭い直感",
    "偏財": "社交家・商才・行動力。お金や人脈が集まりやすい",
    "正財": "堅実・誠実・安定志向。コツコツと確実に財を築く",
    "偏官": "リーダーシップ・決断力・正義感。困難に立ち向かう強さ",
    "正官": "品格・責任感・信頼。組織の中で自然と上に立つ器",
    "偏印": "知的好奇心・独創性・直感型。型にはまらない発想",
    "印綬": "知性・学問・温厚。深い教養と穏やかな人間性",
}

# 日柱の性格テンプレート
NICHIKAN_CHARACTER = {
    "甲": "大木のように真っ直ぐで正義感が強い。リーダー気質で、困難にも根を張って立ち向かう",
    "乙": "草花のようにしなやかで柔軟。環境に適応する力があり、周囲との調和を大切にする",
    "丙": "太陽のように明るく情熱的。周囲を照らし温める存在で、行動力にあふれている",
    "丁": "灯火のように繊細で温かい。内に秘めた情熱があり、人の心を深く理解できる",
    "戊": "山のようにどっしりと安定。信頼感があり、周囲の支えとなる包容力を持つ",
    "己": "大地のように優しく受容的。面倒見がよく、人を育てる力に恵まれている",
    "庚": "鋼のように強く鋭い。決断力と実行力に優れ、困難を突破する力を持つ",
    "辛": "宝石のように美しく繊細。審美眼に優れ、細部にまでこだわる完璧主義者",
    "壬": "大海のように広く深い。スケールの大きな発想と、流れるような行動力を持つ",
    "癸": "雨露のように静かで浸透力がある。知性に優れ、水面下で物事を動かす力を持つ",
}


# ============================================================
# 月の節気（太陽暦での月の区切り）
# ============================================================
# 四柱推命では節入り日で月が変わる（概算値）
SETSU_DATES = {
    1:  (2, 4),   # 立春 → 寅月開始
    2:  (3, 6),   # 啓蟄 → 卯月開始
    3:  (4, 5),   # 清明 → 辰月開始
    4:  (5, 6),   # 立夏 → 巳月開始
    5:  (6, 6),   # 芒種 → 午月開始
    6:  (7, 7),   # 小暑 → 未月開始
    7:  (8, 7),   # 立秋 → 申月開始
    8:  (9, 8),   # 白露 → 酉月開始
    9:  (10, 8),  # 寒露 → 戌月開始
    10: (11, 7),  # 立冬 → 亥月開始
    11: (12, 7),  # 大雪 → 子月開始
    12: (1, 6),   # 小寒 → 丑月開始
}


# ============================================================
# 計算ロジック
# ============================================================

def get_year_pillar(year, month, day):
    """年柱を算出（立春基準で年が変わる）"""
    # 立春前なら前年扱い
    if month < 2 or (month == 2 and day < 4):
        year -= 1
    stem = (year - 4) % 10
    branch = (year - 4) % 12
    return TENKAN[stem], CHISHI[branch]


def get_month_pillar(year, month, day):
    """月柱を算出"""
    # 節入り日で月を判定（直接条件分岐）
    # 寅月(0)=立春〜啓蟄, 卯月(1)=啓蟄〜清明, ...
    if (month == 2 and day >= 4) or (month == 3 and day < 6):
        suimei_month = 0   # 寅月
    elif (month == 3 and day >= 6) or (month == 4 and day < 5):
        suimei_month = 1   # 卯月
    elif (month == 4 and day >= 5) or (month == 5 and day < 6):
        suimei_month = 2   # 辰月
    elif (month == 5 and day >= 6) or (month == 6 and day < 6):
        suimei_month = 3   # 巳月
    elif (month == 6 and day >= 6) or (month == 7 and day < 7):
        suimei_month = 4   # 午月
    elif (month == 7 and day >= 7) or (month == 8 and day < 7):
        suimei_month = 5   # 未月
    elif (month == 8 and day >= 7) or (month == 9 and day < 8):
        suimei_month = 6   # 申月
    elif (month == 9 and day >= 8) or (month == 10 and day < 8):
        suimei_month = 7   # 酉月
    elif (month == 10 and day >= 8) or (month == 11 and day < 7):
        suimei_month = 8   # 戌月
    elif (month == 11 and day >= 7) or (month == 12 and day < 7):
        suimei_month = 9   # 亥月
    elif (month == 12 and day >= 7) or (month == 1 and day < 6):
        suimei_month = 10  # 子月
    elif (month == 1 and day >= 6) or (month == 2 and day < 4):
        suimei_month = 11  # 丑月
    else:
        suimei_month = 0   # フォールバック

    # 月の地支（寅=2から始まる）
    branch_idx = (suimei_month + 2) % 12
    branch = CHISHI[branch_idx]

    # 月の天干（年干から算出）
    year_stem, _ = get_year_pillar(year, month, day)
    year_stem_idx = TENKAN.index(year_stem)

    # 年干別の寅月天干開始インデックス
    month_stem_start = {
        0: 2, 1: 4, 2: 6, 3: 8, 4: 0,
        5: 2, 6: 4, 7: 6, 8: 8, 9: 0
    }
    stem_idx = (month_stem_start[year_stem_idx] + suimei_month) % 10
    stem = TENKAN[stem_idx]

    return stem, branch


def get_day_pillar(year, month, day):
    """日柱を算出（基準日からの日数差で計算）"""
    # 基準日: 2000年1月7日 = 甲子（stem=0, branch=0）
    ref = date(2000, 1, 7)
    target = date(year, month, day)
    diff = (target - ref).days

    stem_idx = diff % 10
    branch_idx = diff % 12

    # 負の値に対応
    if stem_idx < 0:
        stem_idx += 10
    if branch_idx < 0:
        branch_idx += 12

    return TENKAN[stem_idx], CHISHI[branch_idx]


def get_hour_pillar(day_stem, hour):
    """時柱を算出（五鼠遁の法）"""
    if hour is None:
        return None, None

    # 時支（2時間刻み、23時は翌日の子扱いとする考えもあるが、ここでは当日区分）
    # 23-01: 子, 01-03: 丑 ...
    hour_idx = ((hour + 1) % 24) // 2
    branch = CHISHI[hour_idx]

    # 時干
    day_stem_idx = TENKAN.index(day_stem)
    # 日干別の時干開始（子刻）インデックス
    # 甲己→甲(0), 乙庚→丙(2), 丙辛→戊(4), 丁壬→庚(6), 戊癸→壬(8)
    stem_start_idx = ((day_stem_idx % 5) * 2) % 10
    stem_idx = (stem_start_idx + hour_idx) % 10
    stem = TENKAN[stem_idx]

    return stem, branch


def get_tsuhensei(day_stem, target_stem):
    """通変星を算出（日干と対象の天干の関係）"""
    day_gogyo_idx = GOGYO_ORDER.index(TENKAN_GOGYO[day_stem])
    target_gogyo_idx = GOGYO_ORDER.index(TENKAN_GOGYO[target_stem])

    diff = (target_gogyo_idx - day_gogyo_idx) % 5

    day_inyo = TENKAN_INYO[day_stem]
    target_inyo = TENKAN_INYO[target_stem]
    same_inyo = (day_inyo == target_inyo)

    return TSUHENSEI.get((diff, same_inyo), "不明")


def get_junishi_un(day_stem, branch):
    """十二運を算出"""
    start = JUNISHI_START[day_stem]
    branch_idx = CHISHI.index(branch)

    # 陽干は順行、陰干は逆行
    if TENKAN_INYO[day_stem] == "陽":
        idx = (branch_idx - start) % 12
    else:
        idx = (start - branch_idx) % 12

    return JUNISHI_UN[idx]


def get_gogyo_balance(pillars):
    """五行バランスを算出"""
    balance = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for stem, branch in pillars:
        balance[TENKAN_GOGYO[stem]] += 1
        balance[CHISHI_GOGYO[branch]] += 1
    return balance


# ============================================================
# メイン関数
# ============================================================

def calculate_meishiki(year, month, day, hour=None):
    """
    命式を算出して辞書で返す
    hour: 0-23 (Noneの場合は三柱)
    """

    # 基礎の三柱算出
    year_stem, year_branch = get_year_pillar(year, month, day)
    month_stem, month_branch = get_month_pillar(year, month, day)
    day_stem, day_branch = get_day_pillar(year, month, day)

    # 時柱算出（オプション）
    hour_stem, hour_branch = get_hour_pillar(day_stem, hour)

    # 通変星
    year_tsuhen = get_tsuhensei(day_stem, year_stem)
    month_tsuhen = get_tsuhensei(day_stem, month_stem)
    hour_tsuhen = get_tsuhensei(day_stem, hour_stem) if hour_stem else None

    # 十二運
    year_junishi = get_junishi_un(day_stem, year_branch)
    month_junishi = get_junishi_un(day_stem, month_branch)
    day_junishi = get_junishi_un(day_stem, day_branch)
    hour_junishi = get_junishi_un(day_stem, hour_branch) if hour_branch else None

    # 五行バランス
    pillars = [
        (year_stem, year_branch),
        (month_stem, month_branch),
        (day_stem, day_branch),
    ]
    if hour_stem:
        pillars.append((hour_stem, hour_branch))
    gogyo = get_gogyo_balance(pillars)

    # 格局（月柱の通変星で仮判定）
    kakkyoku = month_tsuhen + "格"

    result = {
        "birth_date": f"{year}年{month}月{day}日" + (f" {hour}時" if hour is not None else ""),
        "has_hour": hour is not None,
        "year_pillar": {
            "stem": year_stem,
            "branch": year_branch,
            "label": f"{year_stem}{year_branch}（{TENKAN_YOMI[year_stem]}{CHISHI_YOMI[year_branch]}）",
            "tsuhensei": year_tsuhen,
            "junishi_un": year_junishi,
        },
        "month_pillar": {
            "stem": month_stem,
            "branch": month_branch,
            "label": f"{month_stem}{month_branch}（{TENKAN_YOMI[month_stem]}{CHISHI_YOMI[month_branch]}）",
            "tsuhensei": month_tsuhen,
            "junishi_un": month_junishi,
        },
        "day_pillar": {
            "stem": day_stem,
            "branch": day_branch,
            "label": f"{day_stem}{day_branch}（{TENKAN_YOMI[day_stem]}{CHISHI_YOMI[day_branch]}）",
            "junishi_un": day_junishi,
        },
        "hour_pillar": {
            "stem": hour_stem,
            "branch": hour_branch,
            "label": f"{hour_stem}{hour_branch}（{TENKAN_YOMI[hour_stem]}{CHISHI_YOMI[hour_branch]}）" if hour_stem else None,
            "tsuhensei": hour_tsuhen,
            "junishi_un": hour_junishi,
        } if hour_stem else None,
        "nichikan": {
            "stem": day_stem,
            "gogyo": TENKAN_GOGYO[day_stem],
            "inyo": TENKAN_INYO[day_stem],
            "character": NICHIKAN_CHARACTER[day_stem],
        },
        "kakkyoku": kakkyoku,
        "gogyo_balance": gogyo,
        "tsuhensei_meaning": {
            "year": {"star": year_tsuhen, "meaning": TSUHENSEI_MEANING.get(year_tsuhen, "")},
            "month": {"star": month_tsuhen, "meaning": TSUHENSEI_MEANING.get(month_tsuhen, "")},
            "hour": {"star": hour_tsuhen, "meaning": TSUHENSEI_MEANING.get(hour_tsuhen, "")} if hour_tsuhen else None,
        },
    }
    return result


def format_meishiki(result):
    """命式を読みやすいテキストに変換"""
    lines = []
    lines.append(f"【命式】{result['birth_date']}生まれ")
    lines.append("")
    lines.append("=" * 60)
    
    if result.get("has_hour"):
        lines.append(f"  {'':>6}  {'年柱':>6}  {'月柱':>6}  {'日柱':>6}  {'時柱':>6}")
        lines.append("-" * 60)
        y, m, d, h = result["year_pillar"], result["month_pillar"], result["day_pillar"], result["hour_pillar"]
        lines.append(f"  天干    {y['stem']:>4}    {m['stem']:>4}    {d['stem']:>4}    {h['stem']:>4}")
        lines.append(f"  地支    {y['branch']:>4}    {m['branch']:>4}    {d['branch']:>4}    {h['branch']:>4}")
        lines.append(f"  通変星  {y['tsuhensei']:>4}    {m['tsuhensei']:>4}    {'(本人)':>6}    {h['tsuhensei']:>4}")
        lines.append(f"  十二運  {y['junishi_un']:>4}    {m['junishi_un']:>4}    {d['junishi_un']:>4}    {h['junishi_un']:>4}")
    else:
        lines.append(f"  {'':>6}  {'年柱':>6}  {'月柱':>6}  {'日柱':>6}")
        lines.append("-" * 60)
        y, m, d = result["year_pillar"], result["month_pillar"], result["day_pillar"]
        lines.append(f"  天干    {y['stem']:>4}    {m['stem']:>4}    {d['stem']:>4}")
        lines.append(f"  地支    {y['branch']:>4}    {m['branch']:>4}    {d['branch']:>4}")
        lines.append(f"  通変星  {y['tsuhensei']:>4}    {m['tsuhensei']:>4}    {'(本人)':>6}")
        lines.append(f"  十二運  {y['junishi_un']:>4}    {m['junishi_un']:>4}    {d['junishi_un']:>4}")
    
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"日干: {result['nichikan']['stem']}（{TENKAN_YOMI[result['nichikan']['stem']]}）")
    lines.append(f"   → {result['nichikan']['character']}")
    lines.append("")
    lines.append(f"格局: {result['kakkyoku']}")
    lines.append(f"   → {TSUHENSEI_MEANING.get(result['month_pillar']['tsuhensei'], '')}")
    lines.append("")

    gogyo = result["gogyo_balance"]
    lines.append("五行バランス:")
    for g in GOGYO_ORDER:
        bar = "█" * (gogyo[g] * 5)
        lines.append(f"  {g}: {bar} ({gogyo[g]})")

    return "\n".join(lines)


# ============================================================
# テスト
# ============================================================
if __name__ == "__main__":
    import sys
    hour = None
    if len(sys.argv) >= 5:
        y, m, d, hour = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    elif len(sys.argv) == 4:
        y, m, d = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    else:
        y, m, d, hour = 1990, 11, 1, 10
    
    result = calculate_meishiki(y, m, d, hour)
    print(format_meishiki(result))
