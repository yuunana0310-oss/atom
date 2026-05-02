import customtkinter as ctk
from datetime import date
import models.patient as patient_model
from utils.date_calc import remaining_days, to_wareki
from config import DEADLINE_WARNING_DAYS, COLORS, FONT_FAMILY


STATUS_COLORS = {
    "入院中": COLORS["primary"],
    "退院":   COLORS["text_sub"],
    "外来":   COLORS["success"],
    "訪問":   COLORS["warning"],
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
        ctk.CTkLabel(top, text="患者一覧", font=ctk.CTkFont(family=FONT_FAMILY[0], size=22, weight="bold"),
                     text_color=COLORS["primary"]).pack(side="left")
        ctk.CTkButton(top, text="＋ 新規患者を登録", width=160, height=36,
                     font=ctk.CTkFont(family=FONT_FAMILY[0], weight="bold"),
                     fg_color=COLORS["primary"], hover_color=COLORS["secondary"],
                     command=self._new_patient).pack(side="right")
        today = date.today()
        from utils.date_calc import to_wareki
        date_str = to_wareki(today, short=False)
        ctk.CTkLabel(top, text=date_str, font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                     text_color=COLORS["text_sub"]).pack(side="right", padx=16)

        # ---- 検索 & フィルタ ----
        control_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=16,
                                    border_width=1, border_color="#E2E8F0")
        control_frame.pack(fill="x", padx=20, pady=(0, 12))
        
        search_sub = ctk.CTkFrame(control_frame, fg_color="transparent")
        search_sub.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(search_sub, text="🔍", font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 8))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(search_sub, textvariable=self._search_var, width=300,
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                     placeholder_text="氏名・疾患名・病棟などで検索...",
                     border_width=0, fg_color="#F8FAFC").pack(side="left")

        filter_sub = ctk.CTkFrame(control_frame, fg_color="transparent")
        filter_sub.pack(side="right", padx=16)
        self._filter_var = ctk.StringVar(value="すべて")
        for label in ["すべて", "2-3階", "4-5階", "外来", "訪問", "退院"]:
            ctk.CTkRadioButton(
                filter_sub, text=label,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=12),
                variable=self._filter_var, value=label,
                command=self._refresh,
                fg_color=COLORS["accent"], border_color=COLORS["text_sub"]
            ).pack(side="left", padx=8)

        # ---- テーブル ----
        self._table = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=12,
                                         border_width=1, border_color="#EEEEEE")
        self._table.pack(fill="both", expand=True, padx=20, pady=8)

        self._header_btns = {}
        for col, (label, key, width) in enumerate(COLUMNS):
            if key is None:
                lbl = ctk.CTkLabel(
                    self._table, text=label, width=width,
                    font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                    fg_color="transparent", text_color=COLORS["text_sub"]
                )
                lbl.grid(row=0, column=col, padx=2, pady=12, sticky="ew")
            else:
                btn = ctk.CTkButton(
                    self._table, text=self._header_text(label, key),
                    width=width, font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                    fg_color="transparent", text_color=COLORS["text_sub"],
                    hover_color=COLORS["sidebar_hover"], corner_radius=0,
                    command=lambda k=key, l=label: self._sort_by(k, l),
                )
                btn.grid(row=0, column=col, padx=2, pady=12, sticky="ew")
                self._header_btns[key] = (btn, label)
        
        # ヘッダーの下線
        sep = ctk.CTkFrame(self._table, height=1, fg_color="#E2E8F0")
        sep.grid(row=1, column=0, columnspan=len(COLUMNS), sticky="ew")

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
            if int(w.grid_info().get("row", 0)) > 1: # ヘッダーと下線以外
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
            ctk.CTkLabel(self._table, text="該当する患者がいません", 
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=14),
                         text_color=COLORS["text_sub"]).grid(
                row=2, column=0, columnspan=len(COLUMNS), pady=40
            )
            return

        for idx, p in enumerate(patients):
            r = idx + 2 # Header(0), Sep(1) の次から
            deadline_str = p["rehab_deadline"] or ""
            remaining = ""
            alert_prefix = ""
            row_bg = "white" if idx % 2 != 0 else COLORS["sidebar_hover"]
            text_color = COLORS["text_main"]

            if deadline_str:
                dl = date.fromisoformat(deadline_str)
                rem = remaining_days(dl)
                remaining = str(rem)
                if rem < 0:
                    text_color = COLORS["danger"]
                    alert_prefix = "⚠️ "
                elif rem <= DEADLINE_WARNING_DAYS:
                    text_color = COLORS["warning"]
                    alert_prefix = "⏳ "

            values = [
                str(p["id"]),
                alert_prefix + p["name"],
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
                kwargs = {"width": width, "anchor": "w", "fg_color": row_bg,
                          "font": ctk.CTkFont(family=FONT_FAMILY[0], size=12)}
                
                # 特定のカラムに対する色付け
                curr_text_color = text_color if col in [1, 9] else COLORS["text_main"]
                if col == 10: # ステータス
                    curr_text_color = STATUS_COLORS.get(val, COLORS["text_main"])
                
                ctk.CTkLabel(self._table, text=val, text_color=curr_text_color, **kwargs).grid(
                    row=r, column=col, padx=2, pady=0, sticky="ew"
                )

            btn_frame = ctk.CTkFrame(self._table, fg_color=row_bg)
            btn_frame.grid(row=r, column=12, padx=4, sticky="ew")
            ctk.CTkButton(
                btn_frame, text="編集", width=50, height=24,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=11),
                fg_color=COLORS["secondary"],
                command=lambda pid=p["id"]: self._edit(pid)
            ).pack(side="left", padx=2, pady=2)
            ctk.CTkButton(
                btn_frame, text="削除", width=50, height=24,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=11),
                fg_color=COLORS["danger"], hover_color="#B71C1C",
                command=lambda pid=p["id"], nm=p["name"]: self._delete(pid, nm)
            ).pack(side="left", padx=2, pady=2)

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
