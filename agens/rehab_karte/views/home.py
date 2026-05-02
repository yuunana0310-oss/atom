import customtkinter as ctk
from datetime import date
import calendar
from utils.date_calc import to_wareki
import models.visit as visit_model
import models.memo as memo_model

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_COLORS = {5: "#2196F3", 6: "#E57373"}

STATUS_COLORS = {
    "予定":   "#2196F3",
    "実施":   "#4CAF50",
    "未実施": "#E57373",
}


class HomeView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._today = date.today()
        self._selected = self._today
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        # ---- 左パネル ----
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(20, 8), pady=20)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)  # 予定一覧
        left.rowconfigure(4, weight=1)  # メモ欄

        # 今日の日付
        weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
        dow = weekday_jp[self._today.weekday()]
        ctk.CTkLabel(
            left,
            text=to_wareki(self._today, short=False) + f"（{dow}）",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        # ボタン行
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w", pady=(0, 8))
        ctk.CTkButton(
            btn_row, text="＋ 患者追加", width=140,
            command=self._open_patient_form,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="ホワイトボード", width=150,
            fg_color="#7B1FA2", hover_color="#4A148C",
            command=self._open_whiteboard,
        ).pack(side="left")

        # ---- 予定エリア ----
        sched_frame = ctk.CTkFrame(left)
        sched_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        sched_frame.columnconfigure(0, weight=1)
        sched_frame.rowconfigure(1, weight=1)

        self._schedule_title = ctk.CTkLabel(
            sched_frame, text="",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self._schedule_title.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self._schedule_list = ctk.CTkScrollableFrame(sched_frame, height=180)
        self._schedule_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._schedule_list.columnconfigure(0, weight=1)

        # ---- メモエリア ----
        memo_frame = ctk.CTkFrame(left)
        memo_frame.grid(row=4, column=0, sticky="nsew")
        memo_frame.columnconfigure(0, weight=1)
        memo_frame.rowconfigure(1, weight=1)

        memo_title_bar = ctk.CTkFrame(memo_frame, fg_color="transparent")
        memo_title_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        self._memo_title = ctk.CTkLabel(
            memo_title_bar, text="",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self._memo_title.pack(side="left")

        btn_bar = ctk.CTkFrame(memo_title_bar, fg_color="transparent")
        btn_bar.pack(side="right")
        ctk.CTkButton(btn_bar, text="保存", width=60,
                      command=self._save_memo).pack(side="left", padx=2)
        ctk.CTkButton(btn_bar, text="削除", width=60,
                      fg_color="#E57373", hover_color="#C62828",
                      command=self._delete_memo).pack(side="left", padx=2)

        self._memo_box = ctk.CTkTextbox(memo_frame, font=ctk.CTkFont(size=13))
        self._memo_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self._memo_status = ctk.CTkLabel(
            memo_frame, text="", text_color="gray",
            font=ctk.CTkFont(size=11), anchor="e"
        )
        self._memo_status.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 6))

        # ---- 右パネル：カレンダー ----
        self._cal_frame = ctk.CTkFrame(self, width=290)
        self._cal_frame.grid(row=0, column=1, sticky="ns", padx=(0, 20), pady=20)
        self._cal_frame.grid_propagate(False)

        self._build_calendar()
        self._refresh_schedule()
        self._refresh_memo()

    # ------------------------------------------------------------------ #
    #  カレンダー
    # ------------------------------------------------------------------ #

    def _build_calendar(self):
        for w in self._cal_frame.winfo_children():
            w.destroy()

        year, month = self._view_year, self._view_month
        today = self._today
        sel = self._selected

        nav = ctk.CTkFrame(self._cal_frame, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(10, 4))
        ctk.CTkButton(nav, text="＜", width=30,
                      command=self._prev_month).pack(side="left")
        ctk.CTkLabel(
            nav, text=f"{year}年{month}月",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160, anchor="center"
        ).pack(side="left", expand=True)
        ctk.CTkButton(nav, text="＞", width=30,
                      command=self._next_month).pack(side="right")

        header = ctk.CTkFrame(self._cal_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(2, 0))
        for i, wd in enumerate(WEEKDAYS):
            color = WEEKDAY_COLORS.get(i, ("gray10", "gray90"))
            ctk.CTkLabel(header, text=wd, width=36, anchor="center",
                         text_color=color,
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=1)

        cal = calendar.monthcalendar(year, month)
        for week in cal:
            row_frame = ctk.CTkFrame(self._cal_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=8, pady=1)
            for i, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(row_frame, text="", width=36).pack(side="left", padx=1)
                    continue

                d = date(year, month, day)
                is_today = (d == today)
                is_sel = (d == sel) and not is_today

                if is_today:
                    fg, tc = "#2196F3", "white"
                    font = ctk.CTkFont(weight="bold")
                elif is_sel:
                    fg, tc = ("#BBDEFB", "#1565C0"), ("black", "white")
                    font = ctk.CTkFont(weight="bold")
                else:
                    fg = "transparent"
                    tc = WEEKDAY_COLORS.get(i, ("gray10", "gray90"))
                    font = ctk.CTkFont()

                ctk.CTkButton(
                    row_frame, text=str(day), width=36, height=28,
                    fg_color=fg, text_color=tc, font=font,
                    hover_color=("gray85", "gray35"), corner_radius=6,
                    command=lambda d=d: self._select_date(d),
                ).pack(side="left", padx=1)

        if (year, month) != (today.year, today.month):
            ctk.CTkButton(
                self._cal_frame, text="今日", width=80,
                command=self._go_today
            ).pack(pady=(4, 8))
        else:
            ctk.CTkFrame(self._cal_frame, fg_color="transparent", height=8).pack()

    # ------------------------------------------------------------------ #
    #  予定一覧
    # ------------------------------------------------------------------ #

    def _refresh_schedule(self):
        for w in self._schedule_list.winfo_children():
            w.destroy()

        d = self._selected
        weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
        dow = weekday_jp[d.weekday()]
        prefix = "今日" if d == self._today else to_wareki(d)
        self._schedule_title.configure(text=f"{prefix}（{dow}）の予定")

        iso = d.isoformat()
        schedules = visit_model.get_schedules(iso, iso)

        if not schedules:
            ctk.CTkLabel(
                self._schedule_list, text="予定なし",
                text_color="gray", anchor="w"
            ).pack(anchor="w", padx=8, pady=8)
            return

        hdr = ctk.CTkFrame(self._schedule_list, fg_color="transparent")
        hdr.pack(fill="x", pady=(2, 4))
        for text, width in [("時間", 70), ("患者名", 150), ("種別", 55), ("状態", 70)]:
            ctk.CTkLabel(hdr, text=text, width=width,
                         font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left", padx=2)

        for s in schedules:
            row = ctk.CTkFrame(self._schedule_list,
                               fg_color=("gray95", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)
            status_color = STATUS_COLORS.get(s["status"], "gray")
            for text, width in [
                (s["scheduled_time"] or "──", 70),
                (s["patient_name"],            150),
                (s["schedule_type"],           55),
            ]:
                ctk.CTkLabel(row, text=text, width=width, anchor="w").pack(
                    side="left", padx=4, pady=4)
            ctk.CTkLabel(row, text=s["status"], width=70, anchor="w",
                         text_color=status_color,
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)

    # ------------------------------------------------------------------ #
    #  メモ
    # ------------------------------------------------------------------ #

    def _refresh_memo(self):
        d = self._selected
        weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
        dow = weekday_jp[d.weekday()]
        prefix = "今日" if d == self._today else to_wareki(d)
        self._memo_title.configure(text=f"{prefix}（{dow}）のメモ")

        self._memo_box.delete("1.0", "end")
        memo = memo_model.get_by_date(d.isoformat())
        if memo:
            self._memo_box.insert("1.0", memo["content"])
        self._memo_status.configure(text="")

    def _save_memo(self):
        content = self._memo_box.get("1.0", "end").strip()
        memo_model.save(self._selected.isoformat(), content)
        self._memo_status.configure(text="保存しました", text_color="#2196F3")

    def _delete_memo(self):
        from tkinter import messagebox
        if not messagebox.askyesno("削除確認", "このメモを削除しますか？"):
            return
        memo_model.delete(self._selected.isoformat())
        self._memo_box.delete("1.0", "end")
        self._memo_status.configure(text="削除しました", text_color="gray")

    # ------------------------------------------------------------------ #
    #  操作
    # ------------------------------------------------------------------ #

    def _select_date(self, d: date):
        self._selected = d
        self._build_calendar()
        self._refresh_schedule()
        self._refresh_memo()

    def _prev_month(self):
        if self._view_month == 1:
            self._view_year -= 1
            self._view_month = 12
        else:
            self._view_month -= 1
        self._build_calendar()

    def _next_month(self):
        if self._view_month == 12:
            self._view_year += 1
            self._view_month = 1
        else:
            self._view_month += 1
        self._build_calendar()

    def _go_today(self):
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._selected = self._today
        self._build_calendar()
        self._refresh_schedule()
        self._refresh_memo()

    def _open_patient_form(self):
        from views.patient_form import PatientFormDialog
        PatientFormDialog(self)

    def _open_whiteboard(self):
        import subprocess, sys, os
        script = os.path.join(os.path.dirname(__file__), "whiteboard_qt.py")
        subprocess.Popen([sys.executable, script],
                         cwd=os.path.dirname(os.path.dirname(script)))
