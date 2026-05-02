from database.db import get_connection


def get_by_date(memo_date: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM day_memos WHERE memo_date=?", (memo_date,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save(memo_date: str, content: str):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM day_memos WHERE memo_date=?", (memo_date,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE day_memos SET content=?, updated_at=CURRENT_TIMESTAMP
               WHERE memo_date=?""",
            (content, memo_date),
        )
    else:
        conn.execute(
            "INSERT INTO day_memos (memo_date, content) VALUES (?, ?)",
            (memo_date, content),
        )
    conn.commit()
    conn.close()


def delete(memo_date: str):
    conn = get_connection()
    conn.execute("DELETE FROM day_memos WHERE memo_date=?", (memo_date,))
    conn.commit()
    conn.close()
