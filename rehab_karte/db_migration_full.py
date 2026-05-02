import sqlite3
import os

DB_PATH = "data/rehab.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # New Columns to add to rehab_plans
    cols = [
        ("sex", "TEXT"),
        ("age", "INTEGER"),
        ("impairment_respiratory", "TEXT"),
        ("impairment_circulate", "TEXT"),
        ("impairment_skin", "TEXT"),
        ("impairment_pain", "TEXT"),
        ("impairment_visual", "TEXT"),
        ("impairment_hearing", "TEXT"),
        ("impairment_communication", "TEXT"),
        ("env_housing", "TEXT"),
        ("env_family_structure", "TEXT"),
        ("env_occupation", "TEXT"),
        ("env_interests", "TEXT"),
        ("staff_physician", "TEXT"),
        ("staff_ns", "TEXT"),
        ("staff_msw", "TEXT"),
        ("staff_other", "TEXT"),
        ("sign_date_dr", "DATE"),
        ("sign_date_pt", "DATE"),
        ("sign_date_ot", "DATE"),
        ("sign_date_st", "DATE"),
        ("sign_date_ns", "DATE"),
        ("sign_date_msw", "DATE"),
    ]
    
    for col_name, col_type in cols:
        try:
            cursor.execute(f"ALTER TABLE rehab_plans ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError:
            print(f"Column {col_name} already exists.")
            
    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
