-- 日付メモ
CREATE TABLE IF NOT EXISTS day_memos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    memo_date    DATE    NOT NULL UNIQUE,
    content      TEXT    NOT NULL DEFAULT '',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 担当医マスタ
CREATE TABLE IF NOT EXISTS doctors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- スタッフマスタ
CREATE TABLE IF NOT EXISTS staff (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    role       TEXT    CHECK(role IN ('PT','OT','ST','その他')),
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 患者基本情報
CREATE TABLE IF NOT EXISTS patients (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    birth_date     DATE    NOT NULL,
    doctor_name    TEXT,
    disease_name   TEXT,
    onset_date       DATE,
    disease_type     TEXT    CHECK(disease_type IN ('運動器','脳血管','呼吸器','その他')),
    early_bonus_14   DATE,
    early_bonus_30   DATE,
    rehab_deadline   DATE,
    ward           TEXT    CHECK(ward IN ('2-3階','4-5階','外来','訪問')),
    status         TEXT    NOT NULL DEFAULT '入院中'
                           CHECK(status IN ('入院中','退院','外来','訪問')),
    note           TEXT,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 訪問リハビリ予定
CREATE TABLE IF NOT EXISTS visit_schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER NOT NULL REFERENCES patients(id),
    scheduled_date DATE    NOT NULL,
    scheduled_time TIME,
    schedule_type  TEXT    NOT NULL DEFAULT '定期'
                           CHECK(schedule_type IN ('定期','臨時')),
    status         TEXT    NOT NULL DEFAULT '予定'
                           CHECK(status IN ('予定','実施','未実施')),
    note           TEXT,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 訪問実施記録
CREATE TABLE IF NOT EXISTS visit_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id       INTEGER REFERENCES visit_schedules(id),
    patient_id        INTEGER NOT NULL REFERENCES patients(id),
    staff_id          INTEGER REFERENCES staff(id),
    intervention_date DATE    NOT NULL,
    input_date        DATE    NOT NULL DEFAULT (DATE('now')),
    actual_time_start TIME,
    actual_time_end   TIME,
    content           TEXT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 日次割り当て（ホワイトボード）
CREATE TABLE IF NOT EXISTS daily_assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_date   DATE    NOT NULL,
    patient_id   INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    therapist_id INTEGER NOT NULL REFERENCES staff(id)    ON DELETE CASCADE,
    order_index  INTEGER NOT NULL DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(visit_date, patient_id, therapist_id)
);

-- 業務日誌
CREATE TABLE IF NOT EXISTS daily_journals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_date   DATE     NOT NULL UNIQUE,
    draft_content  TEXT,
    edited_content TEXT,
    confirmed_at   DATETIME,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- リハビリテーション総合実施計画書（様式第21号）月次記録【Excelファイル確認後に実装予定】
