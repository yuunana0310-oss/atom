import customtkinter as ctk
from datetime import date
import models.patient as patient_model
from utils.date_calc import remaining_days, to_wareki
from config import DEADLINE_WARNING_DAYS


STATUS_COLORS = {
    "入院中": "#2196F3",
    "退院":   "#9E9E9E",
    "外来":   "#4CAF50",
    "訪問":   "#FF9800",
}

# (ヘッダ表示名, データキー, 幅)  キーNoneは並べ替え不可
COLUMNS = [
    ("ID",      "id",            40),
    ("氏名",    "name",         140),
    ("病棟",    "ward",          80),
    ("疾患種別","disease_type",  80),
    ("疾患名",  "disease_name", 140),
    ("発症日",    "onset_date",     90),
    ("早期加算14","early_bonus_14", 90),
    ("早期加算30","early_bonus_30", 90),
    ("リハ期限",  "rehab_deadline", 90),
    ("残日数",  "_remaining",    60),
    ("ステータス","status",       80),
    ("生年月日", "birth_date",   90),
    ("操作",    None,           120),
]


class PatientListView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._sort_col = "status"   # 初期ソートキー
        self._sort_asc = True
        self._search_text = ""
        self._build()

    def _build(self):
        # ---- タイトル・今日の日付・新規登録 ----
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(top, text="患者一覧", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="＋ 新規登録", width=110, command=self._new_patient).pack(side="right")
        today = date.today()
        weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
        dow = weekday_jp[today.weekday()]
        from utils.date_calc import to_wareki
        date_str = to_wareki(today, short=False) + f"（{dow}）"
        ctk.CTkLabel(top, text=date_str, font=ctk.CTkFont(size=13),
                     text_color="gray").pack(side="right", padx=16)

        # ---- 検索バー ----
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(search_frame, text="検索：").pack(side="left")
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(search_frame, textvariable=self._search_var, width=240,
                     placeholder_text="氏名・疾患名・病棟・ステータス").pack(side="left", padx=6)
        ctk.CTkButton(search_frame, text="クリア", width=60,
                      command=lambda: self._search_var.set("")).pack(side="left")

        # ---- ステータスフィルタ ----
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(filter_frame, text="ステータス：").pack(side="left")
        self._filter_var = ctk.StringVar(value="すべて")
        for label in ["すべて", "2-3階", "4-5階", "外来", "訪問", "退院"]:
            ctk.CTkRadioButton(
                filter_frame, text=label,
                variable=self._filter_var, value=label,
                command=self._refresh
            ).pack(side="left", padx=6)

        # ---- テーブル ----
        self._table = ctk.CTkScrollableFrame(self)
        self._table.pack(fill="both", expand=True, padx=20, pady=8)

        self._header_btns = {}
        for col, (label, key, width) in enumerate(COLUMNS):
            if key is None:
                # 操作列はボタンなし
                ctk.CTkLabel(
                    self._table, text=label, width=width,
                    font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray85", "gray25"), corner_radius=4
                ).grid(row=0, column=col, padx=2, pady=4, sticky="ew")
            else:
                btn = ctk.CTkButton(
                    self._table, text=self._header_text(label, key),
                    width=width, font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    hover_color=("gray75", "gray35"), corner_radius=4,
                    command=lambda k=key, l=label: self._sort_by(k, l),
                )
                btn.grid(row=0, column=col, padx=2, pady=4, sticky="ew")
                self._header_btns[key] = (btn, label)

        self._refresh()

    def _header_text(self, label: str, key: str) -> str:
        if key != self._sort_col:
            return label
        indicator = " ▲" if self._sort_asc else " ▼"
        return label + indicator

    def _sort_by(self, key: str, label: str):
        if self._sort_col == key:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = key
            self._sort_asc = True
        # ヘッダ表示更新
        for k, (btn, lbl) in self._header_btns.items():
            btn.configure(text=self._header_text(lbl, k))
        self._refresh()

    def _on_search(self):
        self._search_text = self._search_var.get().strip().lower()
        self._refresh()

    def _matches_search(self, p: dict) -> bool:
        if not self._search_text:
            return True
        targets = [
            p["name"] or "",
            p["disease_name"] or "",
            p["ward"] or "",
            p["disease_type"] or "",
            p["status"] or "",
            p["doctor_name"] or "",
        ]
        return any(self._search_text in t.lower() for t in targets)

    def _sort_key(self, p: dict):
        key = self._sort_col
        if key == "_remaining":
            dl = p["rehab_deadline"]
            if not dl:
                return 99999
            return remaining_days(date.fromisoformat(dl))
        if key == "id":
            return p.get("id") or 0
        val = p.get(key) or ""
        return val.lower() if isinstance(val, str) else val

    def _birth_with_age(self, birth_str: str) -> str:
        if not birth_str:
            return ""
        try:
            b = date.fromisoformat(birth_str)
            today = date.today()
            age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
            return f"{to_wareki(birth_str)}（{age}歳）"
        except Exception:
            return birth_str

    def _refresh(self):
        for w in self._table.winfo_children():
            if int(w.grid_info().get("row", 0)) > 0:
                w.destroy()

        patients = patient_model.get_all()

        # フィルタ
        f = self._filter_var.get()
        if f in ("2-3階", "4-5階"):
            patients = [p for p in patients if p["status"] == "入院中" and p["ward"] == f]
        elif f != "すべて":
            patients = [p for p in patients if p["status"] == f]

        # 検索フィルタ
        patients = [p for p in patients if self._matches_search(p)]

        # ソート
        patients.sort(key=self._sort_key, reverse=not self._sort_asc)

        if not patients:
            ctk.CTkLabel(self._table, text="該当する患者がいません", text_color="gray").grid(
                row=1, column=0, columnspan=len(COLUMNS), pady=20
            )
            return

        for r, p in enumerate(patients, start=1):
            deadline_str = p["rehab_deadline"] or ""
            remaining = ""
            row_color = None

            if deadline_str:
                dl = date.fromisoformat(deadline_str)
                rem = remaining_days(dl)
                remaining = str(rem)
                if rem < 0:
                    row_color = "#FFCDD2"
                elif rem <= DEADLINE_WARNING_DAYS:
                    row_color = "#FFF9C4"

            values = [
                str(p["id"]),
                p["name"],
                p["ward"] or "",
                p["disease_type"] or "",
                p["disease_name"] or "",
                to_wareki(p["onset_date"]),
                to_wareki(p.get("early_bonus_14") or ""),
                to_wareki(p.get("early_bonus_30") or ""),
                to_wareki(deadline_str),
                remaining,
                p["status"],
                self._birth_with_age(p["birth_date"]),
            ]

            for col, (val, (_, key, width)) in enumerate(zip(values, COLUMNS[:-1])):
                kwargs = {"width": width, "anchor": "w"}
                if row_color:
                    kwargs["fg_color"] = row_color
                if col == 7 and remaining:
                    rem_int = int(remaining)
                    kwargs["text_color"] = "red" if rem_int < 0 else (
                        "#B8860B" if rem_int <= DEADLINE_WARNING_DAYS else ("gray10", "gray90")
                    )
                if col == 8:
                    kwargs["text_color"] = STATUS_COLORS.get(val, "black")
                ctk.CTkLabel(self._table, text=val, **kwargs).grid(
                    row=r, column=col, padx=2, pady=1, sticky="ew"
                )

            btn_frame = ctk.CTkFrame(self._table, fg_color="transparent")
            btn_frame.grid(row=r, column=12, padx=4)
            ctk.CTkButton(
                btn_frame, text="編集", width=55,
                command=lambda pid=p["id"]: self._edit(pid)
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                btn_frame, text="削除", width=55, fg_color="#E57373", hover_color="#C62828",
                command=lambda pid=p["id"], nm=p["name"]: self._delete(pid, nm)
            ).pack(side="left", padx=2)

    def _new_patient(self):
        from views.patient_form import PatientFormDialog
        PatientFormDialog(self, on_save=self._refresh)

    def _edit(self, pid: int):
        from views.patient_form import PatientFormDialog
        PatientFormDialog(self, patient_id=pid, on_save=self._refresh)

    def _delete(self, pid: int, name: str):
        from tkinter import messagebox
        if messagebox.askyesno("削除確認", f"「{name}」を削除しますか？\n※この操作は元に戻せません"):
            patient_model.delete(pid)
            self._refresh()
