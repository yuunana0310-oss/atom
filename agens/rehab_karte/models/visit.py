from database.db import get_connection


def get_schedules(date_from=None, date_to=None) -> list:
    conn = get_connection()
    sql = """
        SELECT vs.*, p.name as patient_name
        FROM visit_schedules vs
        JOIN patients p ON p.id = vs.patient_id
    """
    params = []
    where = []
    if date_from:
        where.append("vs.scheduled_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("vs.scheduled_date <= ?")
        params.append(date_to)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY vs.scheduled_date, vs.scheduled_time"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_schedule(data: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO visit_schedules
           (patient_id, scheduled_date, scheduled_time, schedule_type, status, note)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data["patient_id"],
            data["scheduled_date"],
            data.get("scheduled_time"),
            data.get("schedule_type", "定期"),
            data.get("status", "予定"),
            data.get("note"),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_schedule(schedule_id: int, data: dict):
    conn = get_connection()
    conn.execute(
        """UPDATE visit_schedules SET
           patient_id=?, scheduled_date=?, scheduled_time=?,
           schedule_type=?, status=?, note=?
           WHERE id=?""",
        (
            data["patient_id"],
            data["scheduled_date"],
            data.get("scheduled_time"),
            data.get("schedule_type", "定期"),
            data.get("status", "予定"),
            data.get("note"),
            schedule_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_schedule(schedule_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM visit_schedules WHERE id=?", (schedule_id,))
    conn.execute("DELETE FROM visit_records WHERE schedule_id=?", (schedule_id,))
    conn.commit()
    conn.close()


def get_record_by_schedule(schedule_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM visit_records WHERE schedule_id=?", (schedule_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_records_by_date(intervention_date: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT vr.*, p.name as patient_name, p.ward, p.status as patient_status,
                  s.name as staff_name
           FROM visit_records vr
           JOIN patients p ON p.id = vr.patient_id
           LEFT JOIN staff s ON s.id = vr.staff_id
           WHERE vr.intervention_date = ?
           ORDER BY p.status, p.ward, vr.actual_time_start""",
        (intervention_date,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_direct_record(data: dict) -> int:
    """予定なしで直接記録（入院・外来など）"""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO visit_records
           (schedule_id, patient_id, staff_id, intervention_date,
            actual_time_start, actual_time_end, content)
           VALUES (NULL, ?, ?, ?, ?, ?, ?)""",
        (
            data["patient_id"],
            data.get("staff_id"),
            data["intervention_date"],
            data.get("actual_time_start"),
            data.get("actual_time_end"),
            data.get("content"),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_record(record_id: int, data: dict):
    conn = get_connection()
    conn.execute(
        """UPDATE visit_records SET
           staff_id=?, actual_time_start=?, actual_time_end=?, content=?
           WHERE id=?""",
        (
            data.get("staff_id"),
            data.get("actual_time_start"),
            data.get("actual_time_end"),
            data.get("content"),
            record_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_record(record_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM visit_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


def save_record(data: dict) -> int:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM visit_records WHERE schedule_id=?", (data["schedule_id"],)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE visit_records SET
               staff_id=?, intervention_date=?, actual_time_start=?,
               actual_time_end=?, content=?
               WHERE schedule_id=?""",
            (
                data.get("staff_id"),
                data["intervention_date"],
                data.get("actual_time_start"),
                data.get("actual_time_end"),
                data.get("content"),
                data["schedule_id"],
            ),
        )
        row_id = existing["id"]
    else:
        cur = conn.execute(
            """INSERT INTO visit_records
               (schedule_id, patient_id, staff_id, intervention_date,
                actual_time_start, actual_time_end, content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["schedule_id"],
                data["patient_id"],
                data.get("staff_id"),
                data["intervention_date"],
                data.get("actual_time_start"),
                data.get("actual_time_end"),
                data.get("content"),
            ),
        )
        row_id = cur.lastrowid
    conn.execute(
        "UPDATE visit_schedules SET status='実施' WHERE id=?",
        (data["schedule_id"],),
    )
    conn.commit()
    conn.close()
    return row_id
