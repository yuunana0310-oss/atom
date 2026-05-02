import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta
import models.visit as visit_model
import models.patient as patient_model
import models.staff as staff_model
import utils.soap_generator as soap_gen
from config import COLORS, FONT_FAMILY

SCHEDULE_TYPES = ["定期", "臨時"]
STATUSES = ["予定", "実施", "未実施"]

STATUS_COLORS = {
    "予定":   "#2196F3",
    "実施":   "#4CAF50",
    "未実施": "#E57373",
}

# (ヘッダ表示名, ソートキー, 幅)  キーNoneはソート不可
COLUMNS = [
    ("日付",       "scheduled_date", 100),
    ("時間",       "scheduled_time",  70),
    ("患者名",     "patient_name",   150),
    ("種別",       "schedule_type",   60),
    ("ステータス", "status",          90),
    ("操作",       None,             170),
]


class VisitManagementView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._sort_col = "scheduled_date"
        self._sort_asc = True
        self._search_text = ""
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=30, pady=(30, 10))
        ctk.CTkLabel(top, text="訪問管理", 
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=24, weight="bold"),
                     text_color=COLORS["primary"]).pack(side="left")
        
        # 検索 & フィルタエリア
        control_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=16,
                                    border_width=1, border_color="#E2E8F0")
        control_frame.pack(fill="x", padx=30, pady=10)
        
        search_sub = ctk.CTkFrame(control_frame, fg_color="transparent")
        search_sub.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(search_sub, text="🔍", font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 8))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(search_sub, textvariable=self._search_var, width=280,
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                     placeholder_text="患者名・種別・ステータス...",
                     border_width=0, fg_color="#F8FAFC").pack(side="left")

        filter_sub = ctk.CTkFrame(control_frame, fg_color="transparent")
        filter_sub.pack(side="left", padx=10)
        self._range_var = ctk.StringVar(value="今週")
        for label in ["今日", "今週", "今月", "全期間"]:
            ctk.CTkRadioButton(
                filter_sub, text=label,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=12),
                variable=self._range_var, value=label,
                command=self._refresh,
                fg_color=COLORS["accent"], border_color=COLORS["text_sub"]
            ).pack(side="left", padx=6)
        
        ctk.CTkButton(control_frame, text="＋ 新規予定", width=120, height=36,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                      fg_color=COLORS["accent"], hover_color="#0369A1",
                      command=self._new_schedule).pack(side="right", padx=16)

        # テーブル
        self._table = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=16,
                                           border_width=1, border_color="#E2E8F0")
        self._table.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        self._header_btns = {}
        for col, (label, key, width) in enumerate(COLUMNS):
            if key is None:
                lbl = ctk.CTkLabel(
                    self._table, text=label, width=width,
                    font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                    fg_color="transparent", text_color=COLORS["text_sub"]
                )
                lbl.grid(row=0, column=col, padx=2, pady=12, sticky="ew")
            else:
                btn = ctk.CTkButton(
                    self._table, text=self._header_text(label, key),
                    width=width, font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                    fg_color="transparent", text_color=COLORS["text_sub"],
                    hover_color=COLORS["sidebar_hover"], corner_radius=0,
                    command=lambda k=key, l=label: self._sort_by(k, l),
                )
                btn.grid(row=0, column=col, padx=2, pady=12, sticky="ew")
                self._header_btns[key] = (btn, label)

        # 下線
        sep = ctk.CTkFrame(self._table, height=1, fg_color="#E2E8F0")
        sep.grid(row=1, column=0, columnspan=len(COLUMNS), sticky="ew")

        self._refresh()

    def _header_text(self, label, key):
        if key != self._sort_col:
            return label
        return label + (" ▲" if self._sort_asc else " ▼")

    def _sort_by(self, key, label):
        if self._sort_col == key:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = key
            self._sort_asc = True
        for k, (btn, lbl) in self._header_btns.items():
            btn.configure(text=self._header_text(lbl, k))
        self._refresh()

    def _on_search(self):
        self._search_text = self._search_var.get().strip().lower()
        self._refresh()

    def _get_date_range(self):
        today = date.today()
        r = self._range_var.get()
        if r == "今日":
            return today.isoformat(), today.isoformat()
        elif r == "今週":
            monday = today - timedelta(days=today.weekday())
            return monday.isoformat(), (monday + timedelta(days=6)).isoformat()
        elif r == "今月":
            first = today.replace(day=1)
            if today.month == 12:
                last = today.replace(day=31)
            else:
                last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            return first.isoformat(), last.isoformat()
        return None, None

    def _refresh(self):
        for w in self._table.winfo_children():
            if int(w.grid_info().get("row", 0)) > 1:
                w.destroy()

        date_from, date_to = self._get_date_range()
        schedules = visit_model.get_schedules(date_from, date_to)

        # 検索フィルタ
        if self._search_text:
            schedules = [
                s for s in schedules
                if self._search_text in (s["patient_name"] or "").lower()
                or self._search_text in (s["schedule_type"] or "").lower()
                or self._search_text in (s["status"] or "").lower()
            ]

        # ソート
        def sort_key(s):
            val = s.get(self._sort_col) or ""
            return val.lower() if isinstance(val, str) else val
        schedules.sort(key=sort_key, reverse=not self._sort_asc)

        if not schedules:
            ctk.CTkLabel(self._table, text="該当する予定がありません", 
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=14),
                         text_color=COLORS["text_sub"]).grid(
                row=2, column=0, columnspan=len(COLUMNS), pady=40)
            return

        for idx, s in enumerate(schedules):
            r = idx + 2
            row_bg = "white" if idx % 2 != 0 else COLORS["sidebar_hover"]
            values = [
                s["scheduled_date"],
                s["scheduled_time"] or "",
                s["patient_name"],
                s["schedule_type"],
                s["status"],
            ]
            for col, (val, (_, key, width)) in enumerate(zip(values, COLUMNS[:-1])):
                kwargs = {"width": width, "anchor": "w", "fg_color": row_bg,
                          "font": ctk.CTkFont(family=FONT_FAMILY[0], size=12)}
                if col == 4:
                    kwargs["text_color"] = STATUS_COLORS.get(val, COLORS["text_main"])
                else:
                    kwargs["text_color"] = COLORS["text_main"]
                    
                ctk.CTkLabel(self._table, text=val, **kwargs).grid(
                    row=r, column=col, padx=2, pady=0, sticky="ew"
                )

            btn_frame = ctk.CTkFrame(self._table, fg_color=row_bg)
            btn_frame.grid(row=r, column=5, padx=4, sticky="ew")

            if s["status"] != "実施":
                ctk.CTkButton(
                    btn_frame, text="記録", width=50,
                    fg_color="#4CAF50", hover_color="#388E3C",
                    command=lambda s=s: self._record(s),
                ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_frame, text="編集", width=50,
                command=lambda s=s: self._edit(s),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                btn_frame, text="削除", width=50,
                fg_color="#E57373", hover_color="#C62828",
                command=lambda s=s: self._delete(s),
            ).pack(side="left", padx=2)

    def _new_schedule(self):
        ScheduleFormDialog(self, on_save=self._refresh)

    def _edit(self, s: dict):
        ScheduleFormDialog(self, schedule=s, on_save=self._refresh)

    def _record(self, s: dict):
        RecordFormDialog(self, schedule=s, on_save=self._refresh)

    def _delete(self, s: dict):
        if messagebox.askyesno(
            "削除確認",
            f"「{s['patient_name']}」{s['scheduled_date']} の訪問予定を削除しますか？",
        ):
            visit_model.delete_schedule(s["id"])
            self._refresh()


class ScheduleFormDialog(ctk.CTkToplevel):
    def __init__(self, master, schedule=None, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._schedule = schedule
        self._on_save = on_save
        self.title("訪問予定登録" if schedule is None else "訪問予定編集")
        self.geometry("420x420")
        self.grab_set()
        self._build()
        if schedule:
            self._load(schedule)

    def _build(self):
        pad = {"padx": 16, "pady": 6}

        def row(label, widget_factory, r):
            ctk.CTkLabel(self, text=label, anchor="w", width=120).grid(
                row=r, column=0, sticky="w", **pad
            )
            w = widget_factory()
            w.grid(row=r, column=1, sticky="ew", **pad)
            return w

        self.columnconfigure(1, weight=1)

        patients = patient_model.get_all()
        self._patient_map = {p["name"]: p["id"] for p in patients}
        patient_names = [p["name"] for p in patients]
        self._patient_combo = ctk.CTkComboBox(self, values=patient_names, width=200)
        if patient_names:
            self._patient_combo.set(patient_names[0])
        ctk.CTkLabel(self, text="患者 *", anchor="w", width=120).grid(
            row=0, column=0, sticky="w", **pad)
        self._patient_combo.grid(row=0, column=1, sticky="ew", **pad)

        self._date_var = ctk.StringVar(value=date.today().isoformat())
        row("訪問日 *\n(YYYY-MM-DD)", lambda: ctk.CTkEntry(self, textvariable=self._date_var), 1)

        self._time_var = ctk.StringVar()
        row("訪問時間\n(HH:MM)", lambda: ctk.CTkEntry(self, textvariable=self._time_var), 2)

        self._type_var = ctk.StringVar(value="定期")
        row("種別", lambda: ctk.CTkOptionMenu(
            self, variable=self._type_var, values=SCHEDULE_TYPES,
        ), 3)

        self._status_var = ctk.StringVar(value="予定")
        row("ステータス", lambda: ctk.CTkOptionMenu(
            self, variable=self._status_var, values=STATUSES,
        ), 4)

        ctk.CTkLabel(self, text="備考", anchor="w").grid(row=5, column=0, sticky="nw", **pad)
        self._note_box = ctk.CTkTextbox(self, height=60)
        self._note_box.grid(row=5, column=1, sticky="ew", **pad)

        ctk.CTkButton(self, text="保存", command=self._save).grid(
            row=6, column=0, columnspan=2, pady=16,
        )

    def _load(self, s: dict):
        self._patient_combo.set(s["patient_name"])
        self._date_var.set(s["scheduled_date"])
        self._time_var.set(s["scheduled_time"] or "")
        self._type_var.set(s["schedule_type"])
        self._status_var.set(s["status"])
        self._note_box.insert("1.0", s["note"] or "")

    def _save(self):
        patient_name = self._patient_combo.get()
        scheduled_date = self._date_var.get().strip()
        if not patient_name or not scheduled_date:
            messagebox.showwarning("入力エラー", "患者と訪問日は必須です")
            return
        patient_id = self._patient_map.get(patient_name)
        if not patient_id:
            messagebox.showwarning("入力エラー", "患者が見つかりません")
            return
        data = {
            "patient_id": patient_id,
            "scheduled_date": scheduled_date,
            "scheduled_time": self._time_var.get().strip() or None,
            "schedule_type": self._type_var.get(),
            "status": self._status_var.get(),
            "note": self._note_box.get("1.0", "end").strip(),
        }
        if self._schedule:
            visit_model.update_schedule(self._schedule["id"], data)
        else:
            visit_model.create_schedule(data)
        if self._on_save:
            self._on_save()
        self.destroy()


class RecordFormDialog(ctk.CTkToplevel):
    def __init__(self, master, schedule: dict, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._schedule = schedule
        self._on_save = on_save
        self.title(f"実施記録 — {schedule['patient_name']}  {schedule['scheduled_date']}")
        self.geometry("500x620")
        self.grab_set()
        self._build()
        self._load_existing()

    def _build(self):
        pad = {"padx": 16, "pady": 5}

        def row(label, widget_factory, r):
            ctk.CTkLabel(self, text=label, anchor="w", width=120).grid(
                row=r, column=0, sticky="w", **pad
            )
            w = widget_factory()
            w.grid(row=r, column=1, sticky="ew", **pad)
            return w

        self.columnconfigure(1, weight=1)

        # ── スタッフ・日時 ──
        staffs = staff_model.get_all(active_only=True)
        self._staff_map = {s["name"]: s["id"] for s in staffs}
        staff_names = ["（未選択）"] + [s["name"] for s in staffs]
        self._staff_combo = ctk.CTkComboBox(self, values=staff_names, width=200)
        self._staff_combo.set(staff_names[0])
        ctk.CTkLabel(self, text="担当スタッフ", anchor="w", width=120).grid(
            row=0, column=0, sticky="w", **pad)
        self._staff_combo.grid(row=0, column=1, sticky="ew", **pad)

        self._date_var = ctk.StringVar(value=self._schedule["scheduled_date"])
        row("実施日 *\n(YYYY-MM-DD)", lambda: ctk.CTkEntry(self, textvariable=self._date_var), 1)

        self._start_var = ctk.StringVar(value=self._schedule["scheduled_time"] or "")
        row("開始時間\n(HH:MM)", lambda: ctk.CTkEntry(self, textvariable=self._start_var), 2)

        self._end_var = ctk.StringVar()
        row("終了時間\n(HH:MM)", lambda: ctk.CTkEntry(self, textvariable=self._end_var), 3)

        # ── SOAP生成セクション ──
        sep = ctk.CTkFrame(self, height=1, fg_color="gray60")
        sep.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 4))

        # オンライン状態チェックとラベル
        online = soap_gen.is_available()
        ai_label_text = "🤖 AI SOAP生成（オンライン）" if online else "🤖 AI SOAP生成（オフライン中）"
        ai_label_color = "#4CAF50" if online else "gray"
        ctk.CTkLabel(self, text=ai_label_text, text_color=ai_label_color,
                     font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        ctk.CTkLabel(self, text="S（主訴）", anchor="w").grid(row=6, column=0, sticky="nw", **pad)
        self._s_box = ctk.CTkTextbox(self, height=50)
        self._s_box.grid(row=6, column=1, sticky="ew", **pad)

        ctk.CTkLabel(self, text="O（所見）", anchor="w").grid(row=7, column=0, sticky="nw", **pad)
        self._o_box = ctk.CTkTextbox(self, height=60)
        self._o_box.grid(row=7, column=1, sticky="ew", **pad)

        self._soap_btn = ctk.CTkButton(
            self, text="SOAP を生成",
            fg_color="#1976D2" if online else "gray",
            hover_color="#1565C0" if online else "gray",
            state="normal" if online else "disabled",
            command=self._on_generate,
        )
        self._soap_btn.grid(row=8, column=1, sticky="e", padx=16, pady=4)

        # ── 実施内容（SOAP出力先） ──
        sep2 = ctk.CTkFrame(self, height=1, fg_color="gray60")
        sep2.grid(row=9, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 4))

        ctk.CTkLabel(self, text="実施内容 / SOAP", anchor="w").grid(
            row=10, column=0, sticky="nw", **pad)
        self._content_box = ctk.CTkTextbox(self, height=110)
        self._content_box.grid(row=10, column=1, sticky="ew", **pad)

        ctk.CTkButton(self, text="保存", command=self._save).grid(
            row=11, column=0, columnspan=2, pady=12,
        )

    def _on_generate(self):
        subjective = self._s_box.get("1.0", "end").strip()
        objective = self._o_box.get("1.0", "end").strip()
        if not subjective and not objective:
            messagebox.showwarning("入力不足", "S（主訴）またはO（所見）を入力してください")
            return

        patient_info = (
            f"患者名: {self._schedule['patient_name']}\n"
            f"訪問日: {self._schedule['scheduled_date']}"
        )

        self._soap_btn.configure(text="生成中...", state="disabled")

        def on_success(text):
            self.after(0, lambda: self._apply_soap(text))

        def on_error(msg):
            self.after(0, lambda: self._on_generate_error(msg))

        soap_gen.generate_soap_async(patient_info, subjective, objective, on_success, on_error)

    def _apply_soap(self, text: str):
        self._content_box.delete("1.0", "end")
        self._content_box.insert("1.0", text)
        self._soap_btn.configure(text="SOAP を生成", state="normal")

    def _on_generate_error(self, msg: str):
        self._soap_btn.configure(text="SOAP を生成", state="normal")
        messagebox.showerror("生成エラー", msg)

    def _load_existing(self):
        rec = visit_model.get_record_by_schedule(self._schedule["id"])
        if not rec:
            return
        for name, sid in self._staff_map.items():
            if sid == rec["staff_id"]:
                self._staff_combo.set(name)
                break
        self._date_var.set(rec["intervention_date"] or "")
        self._start_var.set(rec["actual_time_start"] or "")
        self._end_var.set(rec["actual_time_end"] or "")
        self._content_box.delete("1.0", "end")
        self._content_box.insert("1.0", rec["content"] or "")

    def _save(self):
        intervention_date = self._date_var.get().strip()
        if not intervention_date:
            messagebox.showwarning("入力エラー", "実施日は必須です")
            return
        staff_name = self._staff_combo.get()
        staff_id = self._staff_map.get(staff_name)
        data = {
            "schedule_id": self._schedule["id"],
            "patient_id": self._schedule["patient_id"],
            "staff_id": staff_id,
            "intervention_date": intervention_date,
            "actual_time_start": self._start_var.get().strip() or None,
            "actual_time_end": self._end_var.get().strip() or None,
            "content": self._content_box.get("1.0", "end").strip(),
        }
        visit_model.save_record(data)
        if self._on_save:
            self._on_save()
        self.destroy()
