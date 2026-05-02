from database.db import get_connection


def get_all() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM daily_journals ORDER BY journal_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_by_date(journal_date: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM daily_journals WHERE journal_date=?", (journal_date,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save(journal_date: str, draft_content: str = None, edited_content: str = None):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM daily_journals WHERE journal_date=?", (journal_date,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE daily_journals SET
               draft_content=COALESCE(?, draft_content),
               edited_content=?,
               updated_at=CURRENT_TIMESTAMP
               WHERE journal_date=?""",
            (draft_content, edited_content, journal_date),
        )
    else:
        conn.execute(
            """INSERT INTO daily_journals (journal_date, draft_content, edited_content)
               VALUES (?, ?, ?)""",
            (journal_date, draft_content, edited_content),
        )
    conn.commit()
    conn.close()


def confirm(journal_date: str):
    conn = get_connection()
    conn.execute(
        """UPDATE daily_journals SET
           confirmed_at=CURRENT_TIMESTAMP,
           updated_at=CURRENT_TIMESTAMP
           WHERE journal_date=?""",
        (journal_date,),
    )
    conn.commit()
    conn.close()


def generate_draft(journal_date: str) -> str:
    """その日の全実施記録（入院・外来・訪問）から下書きテキストを生成する"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT vr.actual_time_start, vr.actual_time_end, vr.content,
                  p.name as patient_name, p.ward, p.status as patient_status,
                  s.name as staff_name
           FROM visit_records vr
           JOIN patients p ON p.id = vr.patient_id
           LEFT JOIN staff s ON s.id = vr.staff_id
           WHERE vr.intervention_date = ?
           ORDER BY p.status, p.ward, vr.actual_time_start""",
        (journal_date,),
    ).fetchall()
    conn.close()

    if not rows:
        return f"【業務日誌 {journal_date}】\n\n実施記録なし\n"

    # ステータス順に並べてグループ化
    STATUS_ORDER = ["入院中", "外来", "訪問", "退院", "その他"]

    def status_key(r):
        s = r["patient_status"] or "その他"
        return STATUS_ORDER.index(s) if s in STATUS_ORDER else len(STATUS_ORDER)

    from itertools import groupby
    sorted_rows = sorted(rows, key=status_key)

    lines = [f"【業務日誌 {journal_date}】\n"]
    for status, group in groupby(sorted_rows, key=lambda r: r["patient_status"] or "その他"):
        lines.append(f"▼ {status}")
        for r in group:
            time_range = ""
            if r["actual_time_start"]:
                time_range = r["actual_time_start"]
                if r["actual_time_end"]:
                    time_range += f"〜{r['actual_time_end']}"
                time_range = f"（{time_range}）"
            ward = f"　[{r['ward']}]" if r["ward"] else ""
            staff = f"　担当：{r['staff_name']}" if r["staff_name"] else ""
            lines.append(f"■ {r['patient_name']}{ward}{time_range}{staff}")
            if r["content"]:
                for line in r["content"].splitlines():
                    lines.append(f"　{line}")
            lines.append("")
        lines.append("")

    return "\n".join(lines)
