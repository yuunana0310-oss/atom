import customtkinter as ctk
from tkinter import messagebox
import models.doctor as doctor_model


class DoctorMasterView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="担当医マスタ", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=20, pady=(16, 4)
        )

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(form, text="氏名").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self._name_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self._name_var, width=200).grid(row=0, column=1, padx=8)

        ctk.CTkButton(form, text="追加", width=80, command=self._add).grid(row=0, column=2, padx=12)

        list_frame = ctk.CTkScrollableFrame(self, label_text="登録担当医")
        list_frame.pack(fill="both", expand=True, padx=20, pady=8)

        headers = ["氏名", "状態", "操作", "順番"]
        widths = [200, 60, 130, 70]
        for col, (h, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(list_frame, text=h, font=ctk.CTkFont(weight="bold"), width=w).grid(
                row=0, column=col, padx=4, pady=4
            )

        self._list_frame = list_frame
        self._refresh()

    def _refresh(self):
        for widget in self._list_frame.winfo_children():
            if int(widget.grid_info().get("row", 0)) > 0:
                widget.destroy()

        rows = doctor_model.get_all(active_only=False)
        for r, d in enumerate(rows, start=1):
            is_first = (r == 1)
            is_last  = (r == len(rows))

            ctk.CTkLabel(self._list_frame, text=d["name"], width=200, anchor="w").grid(
                row=r, column=0, padx=4, pady=2
            )
            status_text = "有効" if d["is_active"] else "無効"
            status_color = "green" if d["is_active"] else "gray"
            ctk.CTkLabel(
                self._list_frame, text=status_text, width=60, text_color=status_color
            ).grid(row=r, column=1, padx=4)

            btn_frame = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            btn_frame.grid(row=r, column=2, padx=4)
            ctk.CTkButton(
                btn_frame, text="編集", width=55,
                command=lambda d=d: self._edit_dialog(d)
            ).pack(side="left", padx=2)
            toggle_text = "無効化" if d["is_active"] else "有効化"
            ctk.CTkButton(
                btn_frame, text=toggle_text, width=55, fg_color="gray",
                command=lambda d=d: self._toggle(d)
            ).pack(side="left", padx=2)

            ord_frame = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            ord_frame.grid(row=r, column=3, padx=4)
            ctk.CTkButton(
                ord_frame, text="↑", width=28, height=26,
                state="disabled" if is_first else "normal",
                command=lambda rows=rows, r=r: self._move(rows, r-1, -1)
            ).pack(side="left", padx=1)
            ctk.CTkButton(
                ord_frame, text="↓", width=28, height=26,
                state="disabled" if is_last else "normal",
                command=lambda rows=rows, r=r: self._move(rows, r-1, +1)
            ).pack(side="left", padx=1)

    def _move(self, rows: list, idx: int, direction: int):
        a = rows[idx]
        b = rows[idx + direction]
        doctor_model.swap_order(a["id"], b["id"])
        self._refresh()

    def _add(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "氏名を入力してください")
            return
        doctor_model.create(name)
        self._name_var.set("")
        self._refresh()

    def _toggle(self, d: dict):
        new_active = 0 if d["is_active"] else 1
        doctor_model.update(d["id"], d["name"], new_active)
        self._refresh()

    def _edit_dialog(self, d: dict):
        dlg = ctk.CTkToplevel(self)
        dlg.title("担当医編集")
        dlg.geometry("300x140")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="氏名").grid(row=0, column=0, padx=12, pady=10, sticky="w")
        name_var = ctk.StringVar(value=d["name"])
        ctk.CTkEntry(dlg, textvariable=name_var, width=180).grid(row=0, column=1, padx=8)

        def save():
            doctor_model.update(d["id"], name_var.get().strip(), d["is_active"])
            dlg.destroy()
            self._refresh()

        ctk.CTkButton(dlg, text="保存", command=save).grid(
            row=1, column=0, columnspan=2, pady=16
        )
