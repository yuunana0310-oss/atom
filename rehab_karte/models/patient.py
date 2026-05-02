from datetime import date
from database.db import get_connection
from utils.date_calc import calc_rehab_deadline


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


def get_all() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM patients ORDER BY status, name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_by_id(patient_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM patients WHERE id=?", (patient_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create(data: dict) -> int:
    onset = _parse_date(data.get("onset_date"))
    deadline = calc_rehab_deadline(onset, data.get("disease_type", ""))
    conn = get_connection()
    custom_id = data.get("id")
    if custom_id:
        cur = conn.execute(
            """INSERT INTO patients
               (id, name, birth_date, doctor_name, disease_name,
                onset_date, disease_type, early_bonus_14, early_bonus_30,
                rehab_deadline, ward, status, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                custom_id,
                data["name"],
                data["birth_date"],
                data.get("doctor_name"),
                data.get("disease_name"),
                data.get("onset_date"),
                data.get("disease_type"),
                data.get("early_bonus_14"),
                data.get("early_bonus_30"),
                deadline.isoformat() if deadline else None,
                data.get("ward"),
                data.get("status", "入院中"),
                data.get("note"),
            ),
        )
    else:
        cur = conn.execute(
            """INSERT INTO patients
               (name, birth_date, doctor_name, disease_name,
                onset_date, disease_type, early_bonus_14, early_bonus_30,
                rehab_deadline, ward, status, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["name"],
                data["birth_date"],
                data.get("doctor_name"),
                data.get("disease_name"),
                data.get("onset_date"),
                data.get("disease_type"),
                data.get("early_bonus_14"),
                data.get("early_bonus_30"),
                deadline.isoformat() if deadline else None,
                data.get("ward"),
                data.get("status", "入院中"),
                data.get("note"),
            ),
        )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update(patient_id: int, data: dict):
    onset = _parse_date(data.get("onset_date"))
    deadline = calc_rehab_deadline(onset, data.get("disease_type", ""))
    conn = get_connection()
    conn.execute(
        """UPDATE patients SET
           name=?, birth_date=?, doctor_name=?, disease_name=?,
           onset_date=?, disease_type=?, early_bonus_14=?, early_bonus_30=?,
           rehab_deadline=?, ward=?, status=?, note=?,
           updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (
            data["name"],
            data["birth_date"],
            data.get("doctor_name"),
            data.get("disease_name"),
            data.get("onset_date"),
            data.get("disease_type"),
            data.get("early_bonus_14"),
            data.get("early_bonus_30"),
            deadline.isoformat() if deadline else None,
            data.get("ward"),
            data.get("status", "入院中"),
            data.get("note"),
            patient_id,
        ),
    )
    conn.commit()
    conn.close()


def delete(patient_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM patients WHERE id=?", (patient_id,))
    conn.commit()
    conn.close()
