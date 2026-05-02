import customtkinter as ctk
from tkinter import messagebox
from datetime import date
import models.journal as journal_model
import models.visit as visit_model
import models.patient as patient_model
import models.staff as staff_model
from config import COLORS, FONT_FAMILY


class DailyJournalView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._current_date = date.today().isoformat()
        self._build()
        self._refresh_list()
        self._load_journal(self._current_date)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ---- 左パネル：日誌一覧 ----
        left = ctk.CTkFrame(self, width=220, fg_color="white", corner_radius=16,
                            border_width=1, border_color="#E2E8F0")
        left.grid(row=0, column=0, sticky="nsew", padx=(30, 10), pady=30)
        left.grid_propagate(False)
        left.rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="保存済み日誌", 
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
                     text_color=COLORS["primary"]).grid(
            row=0, column=0, sticky="ew", padx=8, pady=(20, 10)
        )
        self._list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        left.columnconfigure(0, weight=1)

        # ---- 右パネル ----
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 30), pady=30)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1) # テキストエリア

        # 日付バー
        date_bar = ctk.CTkFrame(right, fg_color="white", corner_radius=16,
                                border_width=1, border_color="#E2E8F0")
        date_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 20))
        date_bar.columnconfigure(1, weight=1)

        ctk.CTkLabel(date_bar, text="📅 日付：", font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=(16, 4), pady=12)
        self._date_var = ctk.StringVar(value=self._current_date)
        ctk.CTkEntry(date_bar, textvariable=self._date_var, width=120,
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                     border_width=0, fg_color="#F8FAFC").grid(
            row=0, column=1, sticky="w", padx=6
        )
        ctk.CTkButton(date_bar, text="読み込む", width=100, height=32,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                      fg_color=COLORS["secondary"],
                      command=self._on_load_click).grid(row=0, column=2, padx=4)
        ctk.CTkButton(date_bar, text="↻ 下書き生成", width=110, height=32,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                      fg_color=COLORS["accent"],
                      command=self._generate_draft).grid(row=0, column=3, padx=4)

        # マイクボタンの追加
        self._mic_btn = ctk.CTkButton(date_bar, text="🎙️ 音声録音", width=110, height=32,
                                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                                     fg_color="#F44336", hover_color="#D32F2F", command=self._toggle_mic)
        self._mic_btn.grid(row=0, column=4, padx=(4, 16))
        
        self._is_recording = False

        # ステータスラベル
        self._status_label = ctk.CTkLabel(right, text="", text_color=COLORS["text_sub"],
                                          font=ctk.CTkFont(family=FONT_FAMILY[0], size=13))
        self._status_label.grid(row=1, column=0, sticky="w", padx=4, pady=(0, 8))

        # ---- 当日記録エリア ----
        rec_outer = ctk.CTkFrame(right, fg_color="white", corner_radius=16,
                                border_width=1, border_color="#E2E8F0")
        rec_outer.grid(row=2, column=0, sticky="ew", padx=0, pady=(0, 20))
        rec_outer.columnconfigure(0, weight=1)

        rec_header = ctk.CTkFrame(rec_outer, fg_color="transparent")
        rec_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(rec_header, text="当日の実施記録",
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
                     text_color=COLORS["primary"]).pack(side="left")
        ctk.CTkButton(rec_header, text="＋ 記録追加", width=100, height=28,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=12, weight="bold"),
                      fg_color=COLORS["accent"],
                      command=self._add_record).pack(side="right")

        self._records_frame = ctk.CTkScrollableFrame(rec_outer, height=160, fg_color="transparent")
        self._records_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        self._records_frame.columnconfigure(1, weight=1)

        # ---- テキストエリア ----
        editor_frame = ctk.CTkFrame(right, fg_color="white", corner_radius=16,
                                   border_width=1, border_color="#E2E8F0")
        editor_frame.grid(row=4, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)

        self._textbox = ctk.CTkTextbox(editor_frame, font=ctk.CTkFont(family=FONT_FAMILY[0], size=14),
                                      fg_color="transparent", border_width=0)
        self._textbox.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        # ボタン行
        btn_bar = ctk.CTkFrame(right, fg_color="transparent")
        btn_bar.grid(row=5, column=0, sticky="e", padx=0, pady=(15, 0))
        ctk.CTkButton(btn_bar, text="　保存　", width=100, height=40,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
                      fg_color=COLORS["secondary"],
                      command=self._save).pack(side="left", padx=6)
        self._confirm_btn = ctk.CTkButton(
            btn_bar, text="　確定　", width=100, height=40,
            font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
            fg_color=COLORS["success"], hover_color="#059669",
            command=self._confirm,
        )
        self._confirm_btn.pack(side="left", padx=6)

    # ------------------------------------------------------------------ #

    def _refresh_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        journals = journal_model.get_all()
        if not journals:
            ctk.CTkLabel(self._list_frame, text="なし", text_color="gray").pack(pady=8)
            return

        for j in journals:
            confirmed = bool(j["confirmed_at"])
            indicator = " ✓" if confirmed else ""
            color = "#4CAF50" if confirmed else ("gray70" if j["edited_content"] else "gray50")
            btn = ctk.CTkButton(
                self._list_frame,
                text=f"{j['journal_date']}{indicator}",
                width=170, anchor="w",
                fg_color="transparent",
                text_color=color,
                hover_color=("gray85", "gray30"),
                command=lambda d=j["journal_date"]: self._select_date(d),
            )
            btn.pack(fill="x", padx=2, pady=1)

    def _refresh_records(self):
        for w in self._records_frame.winfo_children():
            w.destroy()

        records = visit_model.get_records_by_date(self._current_date)
        if not records:
            ctk.CTkLabel(self._records_frame, text="記録なし", text_color="gray").grid(
                row=0, column=0, pady=4
            )
            return

        headers = ["患者名", "ステータス", "時間", "担当", "操作"]
        widths = [120, 70, 100, 80, 100]
        for col, (h, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                self._records_frame, text=h, width=w,
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=col, padx=2, pady=2)

        for r, rec in enumerate(records, start=1):
            time_str = rec["actual_time_start"] or ""
            if rec["actual_time_end"]:
                time_str += f"〜{rec['actual_time_end']}"

            vals = [
                rec["patient_name"],
                rec["patient_status"] or "",
                time_str,
                rec["staff_name"] or "",
            ]
            for col, (val, w) in enumerate(zip(vals, widths)):
                ctk.CTkLabel(self._records_frame, text=val, width=w, anchor="w").grid(
                    row=r, column=col, padx=2, pady=1
                )

            btn_frame = ctk.CTkFrame(self._records_frame, fg_color="transparent")
            btn_frame.grid(row=r, column=4, padx=2)
            ctk.CTkButton(
                btn_frame, text="編集", width=45,
                command=lambda rec=rec: self._edit_record(rec)
            ).pack(side="left", padx=1)
            ctk.CTkButton(
                btn_frame, text="削除", width=45,
                fg_color="#E57373", hover_color="#C62828",
                command=lambda rec=rec: self._delete_record(rec)
            ).pack(side="left", padx=1)

    def _select_date(self, d: str):
        self._date_var.set(d)
        self._load_journal(d)

    def _on_load_click(self):
        self._load_journal(self._date_var.get().strip())

    def _load_journal(self, d: str):
        self._current_date = d
        self._textbox.delete("1.0", "end")
        self._refresh_records()
        j = journal_model.get_by_date(d)
        if j:
            content = j["edited_content"] or j["draft_content"] or ""
            self._textbox.insert("1.0", content)
            if j["confirmed_at"]:
                self._status_label.configure(
                    text=f"確定済み：{j['confirmed_at']}", text_color="#4CAF50"
                )
                self._textbox.configure(state="disabled")
                self._confirm_btn.configure(state="disabled")
            else:
                self._status_label.configure(text="下書き", text_color="gray")
                self._textbox.configure(state="normal")
                self._confirm_btn.configure(state="normal")
        else:
            self._status_label.configure(text="未作成", text_color="gray")
            self._textbox.configure(state="normal")
            self._confirm_btn.configure(state="normal")

    def _toggle_mic(self):
        try:
            from utils.audio_recognizer import AudioRecognizer
            recognizer = AudioRecognizer.get_instance()
        except Exception as e:
            messagebox.showerror("エラー", f"音声機能がロードできません:\n{e}")
            return
            
        if not self._is_recording:
            try:
                recognizer.start_recording()
                self._is_recording = True
                self._mic_btn.configure(text="⏹️ 停止中...", fg_color="#FF9800", hover_color="#F57C00")
                self._status_label.configure(text="録音中...", text_color="#F44336")
            except Exception as e:
                messagebox.showerror("エラー", f"録音開始に失敗しました:\n{e}")
        else:
            self._status_label.configure(text="文字起こし中...", text_color="#FF9800")
            self.update_idletasks() # UIを更新
            
            try:
                text = recognizer.stop_recording_and_transcribe()
                if text:
                    self._textbox.configure(state="normal")
                    self._textbox.insert("end", "\n" + text)
                self._status_label.configure(text="文字起こし完了", text_color="#4CAF50")
            except Exception as e:
                messagebox.showerror("エラー", f"文字起こしに失敗しました:\n{e}")
            finally:
                self._is_recording = False
                self._mic_btn.configure(text="🎙️ マイク録音", fg_color="#F44336", hover_color="#D32F2F")

    def _generate_draft(self):
        d = self._date_var.get().strip()
        j = journal_model.get_by_date(d)
        if j and j["confirmed_at"]:
            messagebox.showinfo("確定済み", "確定済みの日誌は変更できません")
            return
        draft = journal_model.generate_draft(d)
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", draft)
        self._status_label.configure(text="下書き生成済み（未保存）", text_color="#FF9800")

    def _save(self):
        d = self._date_var.get().strip()
        content = self._textbox.get("1.0", "end").strip()
        journal_model.save(d, edited_content=content)
        self._status_label.configure(text="保存しました", text_color="#2196F3")
        self._refresh_list()

    def _confirm(self):
        d = self._date_var.get().strip()
        content = self._textbox.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("確認", "内容が空です")
            return
        if not messagebox.askyesno("確定", f"{d} の業務日誌を確定しますか？\n確定後は編集できません。"):
            return
        journal_model.save(d, edited_content=content)
        journal_model.confirm(d)
        self._load_journal(d)
        self._refresh_list()

    def _add_record(self):
        DirectRecordFormDialog(
            self,
            intervention_date=self._current_date,
            on_save=self._refresh_records,
        )

    def _edit_record(self, rec: dict):
        DirectRecordFormDialog(
            self,
            intervention_date=self._current_date,
            record=rec,
            on_save=self._refresh_records,
        )

    def _delete_record(self, rec: dict):
        if messagebox.askyesno("削除確認", f"「{rec['patient_name']}」の記録を削除しますか？"):
            visit_model.delete_record(rec["id"])
            self._refresh_records()


# ------------------------------------------------------------------ #

class DirectRecordFormDialog(ctk.CTkToplevel):
    """予定なし直接記録（入院・外来・訪問すべて対応）"""

    def __init__(self, master, intervention_date: str, record=None, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._record = record
        self._intervention_date = intervention_date
        self._on_save = on_save
        self.title("実施記録" if record is None else "実施記録編集")
        self.geometry("420x420")
        self.grab_set()
        self._build()
        if record:
            self._load(record)

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
        self._patient_var = ctk.StringVar(value=patient_names[0] if patient_names else "")
        row("患者 *", lambda: ctk.CTkComboBox(
            self, variable=self._patient_var, values=patient_names, width=200,
        ), 0)

        self._date_var = ctk.StringVar(value=self._intervention_date)
        row("実施日 *\n(YYYY-MM-DD)", lambda: ctk.CTkEntry(self, textvariable=self._date_var), 1)

        staffs = staff_model.get_all(active_only=True)
        self._staff_map = {s["name"]: s["id"] for s in staffs}
        staff_names = ["（未選択）"] + [s["name"] for s in staffs]
        self._staff_var = ctk.StringVar(value=staff_names[0])
        row("担当スタッフ", lambda: ctk.CTkComboBox(
            self, variable=self._staff_var, values=staff_names, width=200,
        ), 2)

        self._start_var = ctk.StringVar()
        row("開始時間\n(HH:MM)", lambda: ctk.CTkEntry(self, textvariable=self._start_var), 3)

        self._end_var = ctk.StringVar()
        row("終了時間\n(HH:MM)", lambda: ctk.CTkEntry(self, textvariable=self._end_var), 4)

        ctk.CTkLabel(self, text="実施内容", anchor="w").grid(row=5, column=0, sticky="nw", **pad)
        self._content_box = ctk.CTkTextbox(self, height=90)
        self._content_box.grid(row=5, column=1, sticky="ew", **pad)

        self._is_recording = False
        self._mic_btn = ctk.CTkButton(self, text="🎙️ 音声入力", width=100, fg_color="#F44336", hover_color="#D32F2F", command=self._toggle_mic)
        self._mic_btn.grid(row=5, column=0, sticky="sw", **pad)

        ctk.CTkButton(self, text="保存", command=self._save).grid(
            row=6, column=0, columnspan=2, pady=16,
        )

    def _load(self, rec: dict):
        self._patient_var.set(rec["patient_name"])
        self._date_var.set(rec["intervention_date"] or self._intervention_date)
        if rec.get("staff_name"):
            self._staff_var.set(rec["staff_name"])
        self._start_var.set(rec["actual_time_start"] or "")
        self._end_var.set(rec["actual_time_end"] or "")
        self._content_box.insert("1.0", rec["content"] or "")

    def _toggle_mic(self):
        try:
            from utils.audio_recognizer import AudioRecognizer
            recognizer = AudioRecognizer.get_instance()
        except Exception as e:
            messagebox.showerror("エラー", f"音声機能がロードできません:\n{e}")
            return
            
        if not self._is_recording:
            try:
                recognizer.start_recording()
                self._is_recording = True
                self._mic_btn.configure(text="⏹️ 停止", fg_color="#FF9800")
            except Exception as e:
                messagebox.showerror("エラー", f"録音開始に失敗しました:\n{e}")
        else:
            self._mic_btn.configure(text="⏳ 解析中", fg_color="gray")
            self.update_idletasks()
            try:
                text = recognizer.stop_recording_and_transcribe()
                if text:
                    self._content_box.insert("end", text)
            except Exception as e:
                messagebox.showerror("エラー", f"文字起こしに失敗しました:\n{e}")
            finally:
                self._is_recording = False
                self._mic_btn.configure(text="🎙️ 音声入力", fg_color="#F44336")

    def _save(self):
        patient_name = self._patient_var.get()
        intervention_date = self._date_var.get().strip()
        if not patient_name or not intervention_date:
            messagebox.showwarning("入力エラー", "患者と実施日は必須です")
            return
        patient_id = self._patient_map.get(patient_name)
        if not patient_id:
            messagebox.showwarning("入力エラー", "患者が見つかりません")
            return
        staff_name = self._staff_var.get()
        staff_id = self._staff_map.get(staff_name)
        data = {
            "patient_id": patient_id,
            "staff_id": staff_id,
            "intervention_date": intervention_date,
            "actual_time_start": self._start_var.get().strip() or None,
            "actual_time_end": self._end_var.get().strip() or None,
            "content": self._content_box.get("1.0", "end").strip(),
        }
        if self._record:
            visit_model.update_record(self._record["id"], data)
        else:
            visit_model.save_direct_record(data)
        if self._on_save:
            self._on_save()
        self.destroy()
