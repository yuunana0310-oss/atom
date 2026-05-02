import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta
import models.patient as patient_model
import models.doctor as doctor_model
from utils.date_calc import parse_date_input, to_wareki
from config import DEADLINE_WARNING_DAYS, COLORS, FONT_FAMILY

DISEASE_TYPES = ["運動器", "脳血管", "呼吸器", "その他"]
WARDS = ["2-3階", "4-5階", "外来", "訪問"]
STATUSES = ["入院中", "退院", "外来", "訪問"]

_DATE_HINT = "例: 1/6, R8.1.6, 2026-01-06"


class PatientFormDialog(ctk.CTkToplevel):
    """新規登録・編集ダイアログ（patient_id=None で新規）"""

    def __init__(self, master, patient_id=None, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._patient_id = patient_id
        self._on_save = on_save
        self.title("患者登録" if patient_id is None else "患者編集")
        self.geometry("480x720")
        self.grab_set()
        self._build()
        if patient_id:
            self._load(patient_id)

    def _build(self):
        self.configure(fg_color="white")
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color=COLORS["accent"], height=60, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(header, text=self.title(), 
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=18, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        pad = {"padx": 24, "pady": 6}
        self.columnconfigure(1, weight=1)
        
        # スペーサー
        ctk.CTkLabel(self, text="", height=10).grid(row=1, column=0)

        def lbl(text, r):
            ctk.CTkLabel(self, text=text, anchor="w", width=100,
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="normal"),
                         text_color=COLORS["text_main"]).grid(
                row=r, column=0, sticky="w", **pad)

        def entry(var, r, placeholder=""):
            e = ctk.CTkEntry(self, textvariable=var, placeholder_text=placeholder,
                             font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                             border_width=1, border_color="#E2E8F0", fg_color="#F8FAFC")
            e.grid(row=r, column=1, sticky="ew", **pad)
            return e

        def hint_label(r):
            h = ctk.CTkLabel(self, text="", text_color=COLORS["text_sub"],
                               font=ctk.CTkFont(family=FONT_FAMILY[0], size=11), anchor="w")
            h.grid(row=r, column=1, sticky="w", padx=26, pady=(0, 2))
            return h

        # 患者ID  (row 2)
        r_idx = 2
        self._id_var = ctk.StringVar()
        lbl("患者ID", r_idx)
        if self._patient_id:
            self._id_label = ctk.CTkLabel(self, text=str(self._patient_id), anchor="w",
                                          font=ctk.CTkFont(family=FONT_FAMILY[0], weight="bold"),
                                          text_color=COLORS["primary"])
            self._id_label.grid(row=r_idx, column=1, sticky="w", **pad)
        else:
            ctk.CTkEntry(self, textvariable=self._id_var,
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                         placeholder_text="空欄で自動採番",
                         border_width=1, border_color="#E2E8F0", fg_color="#F8FAFC").grid(
                row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # 氏名  (row 3)
        self._name_var = ctk.StringVar()
        lbl("氏名 *", r_idx)
        entry(self._name_var, r_idx)
        r_idx += 1

        # 生年月日  (row 4, 5)
        self._birth_var = ctk.StringVar()
        lbl("生年月日 *", r_idx)
        entry(self._birth_var, r_idx, _DATE_HINT)
        r_idx += 1
        self._birth_hint = hint_label(r_idx)
        self._birth_var.trace_add("write", lambda *_: self._update_birth_hint())
        r_idx += 1

        # 担当医  (row 6)
        lbl("担当医", r_idx)
        doctor_names = doctor_model.get_names()
        self._doctor_combo = ctk.CTkComboBox(
            self, values=doctor_names if doctor_names else [""],
            font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
            border_width=1, border_color="#E2E8F0", fg_color="#F8FAFC",
            button_color=COLORS["accent"], button_hover_color="#0369A1")
        self._doctor_combo.set("")
        self._doctor_combo.grid(row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # 疾患名  (row 7)
        self._disease_var = ctk.StringVar()
        lbl("疾患名", r_idx)
        entry(self._disease_var, r_idx)
        r_idx += 1

        # 発症日  (row 8, 9)
        self._onset_var = ctk.StringVar()
        lbl("発症日", r_idx)
        entry(self._onset_var, r_idx, _DATE_HINT)
        r_idx += 1
        self._onset_hint = hint_label(r_idx)
        self._onset_var.trace_add("write", lambda *_: self._on_onset_changed())
        r_idx += 1

        # 早期加算14  (row 10)
        lbl("早期加算14", r_idx)
        row10 = ctk.CTkFrame(self, fg_color="transparent")
        row10.grid(row=r_idx, column=1, sticky="w", **pad)
        self._bonus14_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row10, text="あり", variable=self._bonus14_var,
                        font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                        fg_color=COLORS["accent"],
                        command=self._on_onset_changed, width=60).pack(side="left")
        self._bonus14_lbl = ctk.CTkLabel(row10, text="", text_color=COLORS["text_sub"],
                                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=11), width=160, anchor="w")
        self._bonus14_lbl.pack(side="left", padx=6)
        r_idx += 1

        # 早期加算30  (row 11)
        lbl("早期加算30", r_idx)
        row11 = ctk.CTkFrame(self, fg_color="transparent")
        row11.grid(row=r_idx, column=1, sticky="w", **pad)
        self._bonus30_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row11, text="あり", variable=self._bonus30_var,
                        font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                        fg_color=COLORS["accent"],
                        command=self._on_onset_changed, width=60).pack(side="left")
        self._bonus30_lbl = ctk.CTkLabel(row11, text="", text_color=COLORS["text_sub"],
                                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=11), width=160, anchor="w")
        self._bonus30_lbl.pack(side="left", padx=6)
        r_idx += 1

        # 疾患種別  (row 12)
        self._dtype_var = ctk.StringVar(value="運動器")
        lbl("疾患種別", r_idx)
        ctk.CTkOptionMenu(self, variable=self._dtype_var, values=DISEASE_TYPES,
                          font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                          fg_color=COLORS["accent"], button_color="#0369A1").grid(
            row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # 病棟 (row 13)
        self._ward_var = ctk.StringVar(value="2-3階")
        lbl("病棟", r_idx)
        ctk.CTkOptionMenu(self, variable=self._ward_var, values=WARDS,
                          font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                          fg_color=COLORS["accent"], button_color="#0369A1").grid(
            row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # ステータス (row 14)
        self._status_var = ctk.StringVar(value="入院中")
        lbl("ステータス", r_idx)
        ctk.CTkOptionMenu(self, variable=self._status_var, values=STATUSES,
                          font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                          fg_color=COLORS["accent"], button_color="#0369A1").grid(
            row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # 備考 (row 15)
        ctk.CTkLabel(self, text="備考", anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="normal")).grid(
            row=r_idx, column=0, sticky="nw", **pad)
        self._note_box = ctk.CTkTextbox(self, height=70, font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                                       border_width=1, border_color="#E2E8F0", fg_color="#F8FAFC")
        self._note_box.grid(row=r_idx, column=1, sticky="ew", **pad)
        r_idx += 1

        # 保存ボタン (row 16)
        ctk.CTkButton(self, text="保存する", height=44, corner_radius=12,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
                      fg_color=COLORS["primary"], hover_color=COLORS["secondary"],
                      command=self._save).grid(
            row=r_idx, column=0, columnspan=2, pady=24)

    # ---- イベントハンドラ ----

    def _update_birth_hint(self):
        d = parse_date_input(self._birth_var.get())
        if d:
            today = date.today()
            age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
            self._birth_hint.configure(text=f"（{age}歳）")
        else:
            self._birth_hint.configure(text="")

    def _on_onset_changed(self, *_):
        d = parse_date_input(self._onset_var.get())
        if d:
            self._onset_hint.configure(text=to_wareki(d, short=False))
            b14 = d + timedelta(days=13)
            b30 = d + timedelta(days=29)
            self._bonus14_lbl.configure(
                text=to_wareki(b14) if self._bonus14_var.get() else "")
            self._bonus30_lbl.configure(
                text=to_wareki(b30) if self._bonus30_var.get() else "")
        else:
            self._onset_hint.configure(text="")
            self._bonus14_lbl.configure(text="")
            self._bonus30_lbl.configure(text="")

    # ---- ロード / セーブ ----

    def _load(self, pid: int):
        p = patient_model.get_by_id(pid)
        if not p:
            return
        self._id_var.set(str(p["id"]))
        self._name_var.set(p["name"])
        self._birth_var.set(to_wareki(p["birth_date"]) if p["birth_date"] else "")
        self._doctor_combo.set(p["doctor_name"] or "")
        self._disease_var.set(p["disease_name"] or "")
        self._onset_var.set(to_wareki(p["onset_date"]) if p["onset_date"] else "")
        if p.get("early_bonus_14"):
            self._bonus14_var.set(True)
        if p.get("early_bonus_30"):
            self._bonus30_var.set(True)
        self._dtype_var.set(p["disease_type"] or "運動器")
        self._ward_var.set(p["ward"] or "2-3階")
        self._status_var.set(p["status"] or "入院中")
        self._note_box.insert("1.0", p["note"] or "")
        self._on_onset_changed()

    def _save(self):
        name = self._name_var.get().strip()
        birth_raw = self._birth_var.get().strip()
        if not name or not birth_raw:
            messagebox.showwarning("入力エラー", "氏名と生年月日は必須です")
            return

        birth = parse_date_input(birth_raw)
        if birth is None:
            messagebox.showwarning("入力エラー", f"生年月日の形式が正しくありません\n{_DATE_HINT}")
            return

        onset_iso = None
        onset = None
        onset_raw = self._onset_var.get().strip()
        if onset_raw:
            onset = parse_date_input(onset_raw)
            if onset is None:
                messagebox.showwarning("入力エラー", f"発症日の形式が正しくありません\n{_DATE_HINT}")
                return
            onset_iso = onset.isoformat()

        bonus14_iso = None
        bonus30_iso = None
        if onset:
            if self._bonus14_var.get():
                bonus14_iso = (onset + timedelta(days=13)).isoformat()
            if self._bonus30_var.get():
                bonus30_iso = (onset + timedelta(days=29)).isoformat()

        data = {
            "name": name,
            "birth_date": birth.isoformat(),
            "doctor_name": self._doctor_combo.get().strip(),
            "disease_name": self._disease_var.get().strip(),
            "onset_date": onset_iso,
            "early_bonus_14": bonus14_iso,
            "early_bonus_30": bonus30_iso,
            "disease_type": self._dtype_var.get(),
            "ward": self._ward_var.get(),
            "status": self._status_var.get(),
            "note": self._note_box.get("1.0", "end").strip(),
        }
        try:
            if self._patient_id:
                patient_model.update(self._patient_id, data)
            else:
                custom_id = self._id_var.get().strip()
                if custom_id:
                    try:
                        data["id"] = int(custom_id)
                    except ValueError:
                        messagebox.showwarning("入力エラー", "患者IDは数値で入力してください")
                        return
                patient_model.create(data)
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))
            return
        if self._on_save:
            self._on_save()
        self.destroy()
