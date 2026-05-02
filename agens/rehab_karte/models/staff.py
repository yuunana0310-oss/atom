from database.db import get_connection


def get_all(active_only=True) -> list:
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM staff WHERE is_active=1 ORDER BY order_index, name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM staff ORDER BY order_index, name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create(name: str, role: str) -> int:
    conn = get_connection()
    max_order = conn.execute(
        "SELECT COALESCE(MAX(order_index),0) FROM staff"
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO staff (name, role, order_index) VALUES (?, ?, ?)",
        (name, role, max_order + 1),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def swap_order(id_a: int, id_b: int):
    conn = get_connection()
    oa = conn.execute("SELECT order_index FROM staff WHERE id=?", (id_a,)).fetchone()[0]
    ob = conn.execute("SELECT order_index FROM staff WHERE id=?", (id_b,)).fetchone()[0]
    conn.execute("UPDATE staff SET order_index=? WHERE id=?", (ob, id_a))
    conn.execute("UPDATE staff SET order_index=? WHERE id=?", (oa, id_b))
    conn.commit()
    conn.close()


def update(staff_id: int, name: str, role: str, is_active: int):
    conn = get_connection()
    conn.execute(
        "UPDATE staff SET name=?, role=?, is_active=? WHERE id=?",
        (name, role, is_active, staff_id),
    )
    conn.commit()
    conn.close()


def delete(staff_id: int):
    conn = get_connection()
    conn.execute("UPDATE staff SET is_active=0 WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()
