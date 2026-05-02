from database.db import get_connection


def get_by_date(visit_date: str) -> list:
    """その日の全割り当て（患者・スタッフ情報付き）"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT da.*, p.name AS patient_name, p.ward, p.status AS patient_status,
                  s.name AS therapist_name, s.role AS therapist_role
           FROM daily_assignments da
           JOIN patients p ON p.id = da.patient_id
           JOIN staff    s ON s.id = da.therapist_id
           WHERE da.visit_date = ?
           ORDER BY da.therapist_id, da.order_index""",
        (visit_date,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def exists(visit_date: str, patient_id: int, therapist_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM daily_assignments WHERE visit_date=? AND patient_id=? AND therapist_id=?",
        (visit_date, patient_id, therapist_id),
    ).fetchone()
    conn.close()
    return row is not None


def get_max_order(visit_date: str, therapist_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(MAX(order_index),0) FROM daily_assignments WHERE visit_date=? AND therapist_id=?",
        (visit_date, therapist_id),
    ).fetchone()
    conn.close()
    return row[0]


def create(visit_date: str, patient_id: int, therapist_id: int, order_index: int = 0) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT OR IGNORE INTO daily_assignments (visit_date, patient_id, therapist_id, order_index)
           VALUES (?, ?, ?, ?)""",
        (visit_date, patient_id, therapist_id, order_index),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def delete(assignment_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM daily_assignments WHERE id=?", (assignment_id,))
    conn.commit()
    conn.close()


def reorder(visit_date: str, therapist_id: int, patient_ids: list[int]):
    """patient_ids の順序で order_index を振り直す"""
    conn = get_connection()
    for idx, pid in enumerate(patient_ids):
        conn.execute(
            """UPDATE daily_assignments SET order_index=?
               WHERE visit_date=? AND patient_id=? AND therapist_id=?""",
            (idx, visit_date, pid, therapist_id),
        )
    conn.commit()
    conn.close()
