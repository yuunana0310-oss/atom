import customtkinter as ctk
from tkinter import messagebox
import models.staff as staff_model

ROLES = ["PT", "OT", "ST", "その他"]


class StaffMasterView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._build()

    def _build(self):
        # ---- タイトル ----
        ctk.CTkLabel(self, text="スタッフマスタ", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=20, pady=(16, 4)
        )

        # ---- 入力フォーム ----
        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(form, text="氏名").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self._name_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self._name_var, width=180).grid(row=0, column=1, padx=8)

        ctk.CTkLabel(form, text="職種").grid(row=0, column=2, padx=8, sticky="w")
        self._role_var = ctk.StringVar(value="PT")
        ctk.CTkOptionMenu(form, variable=self._role_var, values=ROLES, width=100).grid(
            row=0, column=3, padx=8
        )

        self._add_btn = ctk.CTkButton(form, text="追加", width=80, command=self._add)
        self._add_btn.grid(row=0, column=4, padx=12)

        # ---- 一覧テーブル ----
        list_frame = ctk.CTkScrollableFrame(self, label_text="登録スタッフ")
        list_frame.pack(fill="both", expand=True, padx=20, pady=8)

        headers = ["氏名", "職種", "状態", "操作", "順番"]
        widths = [160, 80, 60, 130, 70]
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

        rows = staff_model.get_all(active_only=False)
        for r, s in enumerate(rows, start=1):
            is_first = (r == 1)
            is_last  = (r == len(rows))

            ctk.CTkLabel(self._list_frame, text=s["name"], width=160, anchor="w").grid(
                row=r, column=0, padx=4, pady=2
            )
            ctk.CTkLabel(self._list_frame, text=s["role"] or "", width=80).grid(
                row=r, column=1, padx=4
            )
            status_text = "有効" if s["is_active"] else "無効"
            status_color = "green" if s["is_active"] else "gray"
            ctk.CTkLabel(
                self._list_frame, text=status_text, width=60,
                text_color=status_color
            ).grid(row=r, column=2, padx=4)

            btn_frame = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            btn_frame.grid(row=r, column=3, padx=4)
            ctk.CTkButton(
                btn_frame, text="編集", width=55,
                command=lambda s=s: self._edit_dialog(s)
            ).pack(side="left", padx=2)
            toggle_text = "無効化" if s["is_active"] else "有効化"
            ctk.CTkButton(
                btn_frame, text=toggle_text, width=55, fg_color="gray",
                command=lambda s=s: self._toggle(s)
            ).pack(side="left", padx=2)

            ord_frame = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            ord_frame.grid(row=r, column=4, padx=4)
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
        staff_model.swap_order(a["id"], b["id"])
        self._refresh()

    def _add(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "氏名を入力してください")
            return
        staff_model.create(name, self._role_var.get())
        self._name_var.set("")
        self._refresh()

    def _toggle(self, s: dict):
        new_active = 0 if s["is_active"] else 1
        staff_model.update(s["id"], s["name"], s["role"], new_active)
        self._refresh()

    def _edit_dialog(self, s: dict):
        dlg = ctk.CTkToplevel(self)
        dlg.title("スタッフ編集")
        dlg.geometry("320x180")
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="氏名").grid(row=0, column=0, padx=12, pady=10, sticky="w")
        name_var = ctk.StringVar(value=s["name"])
        ctk.CTkEntry(dlg, textvariable=name_var, width=160).grid(row=0, column=1, padx=8)

        ctk.CTkLabel(dlg, text="職種").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        role_var = ctk.StringVar(value=s["role"] or "PT")
        ctk.CTkOptionMenu(dlg, variable=role_var, values=ROLES, width=160).grid(row=1, column=1, padx=8)

        def save():
            staff_model.update(s["id"], name_var.get().strip(), role_var.get(), s["is_active"])
            dlg.destroy()
            self._refresh()

        ctk.CTkButton(dlg, text="保存", command=save).grid(
            row=2, column=0, columnspan=2, pady=16
        )
