import re
from datetime import date, timedelta


DEADLINE_DAYS = {
    "運動器": 149,
    "脳血管": 179,
    "呼吸器":  89,
}

# 元号の開始日
_ERAS = [
    ("R", "令和",  date(2019, 5, 1),  2018),
    ("H", "平成",  date(1989, 1, 8),  1988),
    ("S", "昭和",  date(1926, 12, 25), 1925),
    ("T", "大正",  date(1912, 7, 30), 1911),
]


def fiscal_year_start(today: date | None = None) -> date:
    """当年度の開始日（4月1日）を返す"""
    t = today or date.today()
    year = t.year if t.month >= 4 else t.year - 1
    return date(year, 4, 1)


def parse_date_input(s: str) -> date | None:
    """
    複数フォーマットの日付文字列を date に変換する。
    対応フォーマット:
      - "2026-01-06"  / "2026/01/06"  (ISO / 西暦スラッシュ)
      - "1/6" / "01/06"               (月/日 → 当年度の年を補完)
      - "R8.1.6" / "R8/1/6"           (令和)
      - "H30.4.1"                     (平成)
      - "S60.3.15"                    (昭和)
    """
    s = s.strip()
    if not s:
        return None

    # 西暦 YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    # 西暦 YYYY/MM/DD
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # 元号  R8.1.6 / H30.4.1 / S60.3.15  (区切りは . / -)
    m = re.fullmatch(r"([RrHhSsTt])(\d{1,2})[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        prefix = m.group(1).upper()
        era_y, mo, dy = int(m.group(2)), int(m.group(3)), int(m.group(4))
        for short, _, _, offset in _ERAS:
            if short == prefix:
                try:
                    return date(era_y + offset, mo, dy)
                except ValueError:
                    return None
        return None

    # 月/日のみ (1/6, 01/06) → 当年度で補完
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
        fy = fiscal_year_start()
        # 4月以降 → 年度開始年、1〜3月 → 翌年
        year = fy.year if mo >= 4 else fy.year + 1
        try:
            return date(year, mo, dy)
        except ValueError:
            return None

    return None


def to_wareki(d: date | str | None, short: bool = True) -> str:
    """
    date または ISO文字列 を元号表示に変換する。
    short=True  → "R8.1.6"
    short=False → "令和8年1月6日"
    """
    if d is None:
        return ""
    if isinstance(d, str):
        if not d:
            return ""
        try:
            d = date.fromisoformat(d)
        except ValueError:
            return d  # 変換できなければそのまま返す

    for short_name, long_name, start, offset in _ERAS:
        if d >= start:
            era_y = d.year - offset
            if short:
                return f"{short_name}{era_y}/{d.month}/{d.day}"
            else:
                return f"{long_name}{era_y}年{d.month}月{d.day}日"

    # 明治以前はそのまま西暦
    return d.isoformat()


def calc_rehab_deadline(onset_date: date, disease_type: str) -> date | None:
    days = DEADLINE_DAYS.get(disease_type)
    if days is None or onset_date is None:
        return None
    return onset_date + timedelta(days=days)


def remaining_days(deadline: date) -> int:
    return (deadline - date.today()).days
