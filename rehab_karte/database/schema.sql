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

-- リハビリテーション総合実施計画書（様式第21号）
CREATE TABLE IF NOT EXISTS rehab_plans (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    plan_date            DATE    NOT NULL, -- 計画作成日
    
    -- 基本情報 (スナップショット)
    disease_name         TEXT,     -- 疾患名
    onset_date           DATE,     -- 発症日
    surgery_date         DATE,     -- 手術日
    
    -- 担当者
    doctor_name          TEXT,
    therapist_pt         TEXT,
    therapist_ot         TEXT,
    therapist_st         TEXT,
    
    -- 1. 心身機能・構造
    impairment_consciousness TEXT, -- 意識
    impairment_rom           TEXT, -- ROM
    impairment_muscle        TEXT, -- 筋力
    impairment_paralysis     TEXT, -- 麻痺
    impairment_sensation     TEXT, -- 感覚
    impairment_higher_brain  TEXT, -- 高次脳
    impairment_other         TEXT,
    
    -- 2. 基本動作
    movement_rolling         TEXT,
    movement_sitting         TEXT,
    movement_standing        TEXT,
    movement_walking         TEXT,
    
    -- 3. 日常生活活動 (ADL) - 評価(FIM/BI等)
    -- JSON形式で保存 (項目ごとの 初回/前回/今回/目標 を格納)
    adl_evaluation_json      TEXT, 
    
    -- 栄養・嚥下
    nutrition_status         TEXT,
    nutrition_method         TEXT,
    nutrition_kcal           REAL,
    nutrition_protein        REAL,
    swallowing_fois          INTEGER,
    swallowing_notes         TEXT,
    
    -- 4. 目標
    goal_short               TEXT,
    goal_long                TEXT,
    goal_activity_participation TEXT,
    
    -- リハビリテーション実施内容
    plan_pt                  TEXT,
    plan_ot                  TEXT,
    plan_st                  TEXT,
    
    -- 社会資源・履歴・その他
    social_service           TEXT,
    rehab_history            TEXT,
    other_notes              TEXT,
    
    -- ドクター所見 (検討リスト用)
    doctor_finding           TEXT,
    doctor_policy            TEXT,
    
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME DEFAULT CURRENT_TIMESTAMP
);
