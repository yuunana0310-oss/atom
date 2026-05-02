import customtkinter as ctk
from tkinter import messagebox
import models.doctor as doctor_model
from config import COLORS, FONT_FAMILY


class DoctorMasterView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="担当医マスタ", 
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=24, weight="bold"),
                     text_color=COLORS["primary"]).pack(
            anchor="w", padx=30, pady=(30, 20)
        )

        form = ctk.CTkFrame(self, fg_color="white", corner_radius=16,
                            border_width=1, border_color="#E2E8F0")
        form.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkLabel(form, text="氏名",
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="normal")).grid(row=0, column=0, padx=(20, 4), pady=20, sticky="w")
        self._name_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self._name_var, width=240,
                     font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                     border_width=1, border_color="#E2E8F0", fg_color="#F8FAFC").grid(row=0, column=1, padx=8)

        ctk.CTkButton(form, text="追加", width=100, height=36,
                      font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                      fg_color=COLORS["primary"],
                      command=self._add).grid(row=0, column=2, padx=(20, 20))

        list_outer = ctk.CTkFrame(self, fg_color="white", corner_radius=16,
                                 border_width=1, border_color="#E2E8F0")
        list_outer.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        list_frame = ctk.CTkScrollableFrame(list_outer, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=8, pady=8)

        headers = ["氏名", "状態", "操作", "順番"]
        widths = [240, 100, 150, 80]
        for col, (h, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(list_frame, text=h, 
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                         text_color=COLORS["text_sub"], width=w).grid(
                row=0, column=col, padx=4, pady=12
            )
        
        # ヘッダーの下線
        sep = ctk.CTkFrame(list_frame, height=1, fg_color="#E2E8F0")
        sep.grid(row=1, column=0, columnspan=len(headers), sticky="ew")

        self._list_frame = list_frame
        self._refresh()

    def _refresh(self):
        for widget in self._list_frame.winfo_children():
            if int(widget.grid_info().get("row", 0)) > 1: # ヘッダーと下線以外
                widget.destroy()

        rows = doctor_model.get_all(active_only=False)
        for idx, d in enumerate(rows):
            r = idx + 2
            row_bg = "white" if idx % 2 != 0 else COLORS["sidebar_hover"]
            is_first = (idx == 0)
            is_last  = (idx == len(rows) - 1)

            ctk.CTkLabel(self._list_frame, text=d["name"], width=240, anchor="w",
                         font=ctk.CTkFont(family=FONT_FAMILY[0], size=13),
                         fg_color=row_bg, text_color=COLORS["text_main"]).grid(
                row=r, column=0, padx=4, pady=0, sticky="ew"
            )
            status_text = "有効" if d["is_active"] else "無効"
            status_color = COLORS["success"] if d["is_active"] else COLORS["text_sub"]
            ctk.CTkLabel(
                self._list_frame, text=status_text, width=100,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=13, weight="bold"),
                fg_color=row_bg, text_color=status_color
            ).grid(row=r, column=1, padx=4, pady=0, sticky="ew")

            btn_frame = ctk.CTkFrame(self._list_frame, fg_color=row_bg)
            btn_frame.grid(row=r, column=2, padx=4, sticky="ew")
            ctk.CTkButton(
                btn_frame, text="編集", width=60, height=24,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=11),
                fg_color=COLORS["secondary"],
                command=lambda d=d: self._edit_dialog(d)
            ).pack(side="left", padx=2, pady=4)
            toggle_text = "無効化" if d["is_active"] else "有効化"
            ctk.CTkButton(
                btn_frame, text=toggle_text, width=60, height=24,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=11),
                fg_color=COLORS["text_sub"], hover_color=COLORS["danger"],
                command=lambda d=d: self._toggle(d)
            ).pack(side="left", padx=2, pady=4)

            ord_frame = ctk.CTkFrame(self._list_frame, fg_color=row_bg)
            ord_frame.grid(row=r, column=3, padx=4, sticky="ew")
            ctk.CTkButton(
                ord_frame, text="↑", width=30, height=24,
                fg_color=COLORS["accent"],
                state="disabled" if is_first else "normal",
                command=lambda rows=rows, idx=idx: self._move(rows, idx, -1)
            ).pack(side="left", padx=1, pady=4)
            ctk.CTkButton(
                ord_frame, text="↓", width=30, height=24,
                fg_color=COLORS["accent"],
                state="disabled" if is_last else "normal",
                command=lambda rows=rows, idx=idx: self._move(rows, idx, +1)
            ).pack(side="left", padx=1, pady=4)

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
