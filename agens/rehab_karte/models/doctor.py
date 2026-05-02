from database.db import get_connection


def get_all(active_only=True) -> list:
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM doctors WHERE is_active=1 ORDER BY order_index, name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM doctors ORDER BY order_index, name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_names(active_only=True) -> list[str]:
    return [d["name"] for d in get_all(active_only)]


def create(name: str) -> int:
    conn = get_connection()
    max_order = conn.execute(
        "SELECT COALESCE(MAX(order_index),0) FROM doctors"
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO doctors (name, order_index) VALUES (?, ?)",
        (name, max_order + 1),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update(doctor_id: int, name: str, is_active: int):
    conn = get_connection()
    conn.execute(
        "UPDATE doctors SET name=?, is_active=? WHERE id=?",
        (name, is_active, doctor_id),
    )
    conn.commit()
    conn.close()


def swap_order(id_a: int, id_b: int):
    conn = get_connection()
    oa = conn.execute("SELECT order_index FROM doctors WHERE id=?", (id_a,)).fetchone()[0]
    ob = conn.execute("SELECT order_index FROM doctors WHERE id=?", (id_b,)).fetchone()[0]
    conn.execute("UPDATE doctors SET order_index=? WHERE id=?", (ob, id_a))
    conn.execute("UPDATE doctors SET order_index=? WHERE id=?", (oa, id_b))
    conn.commit()
    conn.close()


def delete(doctor_id: int):
    conn = get_connection()
    conn.execute("UPDATE doctors SET is_active=0 WHERE id=?", (doctor_id,))
    conn.commit()
    conn.close()
