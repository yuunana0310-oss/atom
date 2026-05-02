import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import json
import os
from database.db import get_connection
from config import COLORS, FONT_FAMILY
import webbrowser
from utils.excel_mapper import export_to_excel
from utils.excel_bridge import prepare_editing_excel, scrape_editing_excel
import os

class PaperCell(tk.Frame):
    """A helper to create paper-like table cells with sharp borders."""
    def __init__(self, master, text="", font_size=8, is_header=False, width=None, **kwargs):
        border_color = "black"
        bg = "#F2F2F2" if is_header else "white"
        super().__init__(master, highlightbackground=border_color, highlightthickness=1, bg=bg, **kwargs)
        self.label = tk.Label(self, text=text, font=(FONT_FAMILY[0], font_size, "bold" if is_header else "normal"), 
                              bg=bg, fg="black", anchor="w" if not is_header else "center", padx=1)
        self.label.pack(fill="both", expand=True)

class ChoiceGrid(tk.Frame):
    """Mimics paper choice like ( 自立 ・ 介助 )"""
    def __init__(self, master, options, font_size=8, **kwargs):
        super().__init__(master, bg="white", **kwargs)
        self.vars = {} # Not used for now, just visual mock or simple toggle
        for opt in options:
            btn = tk.Label(self, text=opt, font=(FONT_FAMILY[0], font_size), bg="white", fg="black", cursor="hand2")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, b=btn: self._toggle(b))
    
    def _toggle(self, btn):
        if btn.cget("fg") == "red":
            btn.configure(fg="black", font=(FONT_FAMILY[0], 8, "normal"))
        else:
            btn.configure(fg="red", font=(FONT_FAMILY[0], 8, "bold"))

class ADLTable(tk.Frame):
    def __init__(self, master, items, font_size=8, **kwargs):
        super().__init__(master, bg="black", **kwargs)
        self.items = items
        self.font_size = font_size
        self.entries = {}
        self._setup_ui()

    def _setup_ui(self):
        headers = ["項目", "初回", "前回", "今回", "目標"]
        for i, h in enumerate(headers):
            PaperCell(self, text=h, font_size=self.font_size, is_header=True).grid(row=0, column=i, sticky="nsew")
        
        for r, item in enumerate(self.items):
            PaperCell(self, text=item, font_size=self.font_size).grid(row=r+1, column=0, sticky="nsew")
            for c in range(1, 5):
                f = tk.Frame(self, bg="white", highlightbackground="black", highlightthickness=1)
                f.grid(row=r+1, column=c, sticky="nsew")
                e = tk.Entry(f, width=4, font=(FONT_FAMILY[0], self.font_size), borderwidth=0, justify="center")
                e.pack(padx=1, pady=0)
                self.entries[(item, c)] = e

    def get_data(self):
        return {item: {col: self.entries[(item, col)].get() for col in ["start", "prev", "now", "goal"]} for item in self.items}

    def set_data(self, data):
        if not data: return
        for item, cols in data.items():
            if item in self.items:
                for col, val in cols.items():
                    if (item, col) in self.entries:
                        self.entries[(item, col)].delete(0, "end")
                        self.entries[(item, col)].insert(0, val or "")

class PlanEditorView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.patient_id = None
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._setup_sidebar()
        self._setup_launch_screen()

    def _setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="患者・計画書選択", font=(FONT_FAMILY[0], 14, "bold")).pack(pady=10)
        self.patient_list = tk.Listbox(self.sidebar, bg=COLORS["primary"], fg="white", font=(FONT_FAMILY[0], 11), borderwidth=0)
        self.patient_list.pack(fill="both", expand=True, padx=10, pady=5)
        self.patient_list.bind("<<ListboxSelect>>", self._on_patient_selected)
        
        self._refresh_patients()

    def _refresh_patients(self):
        self.patient_list.delete(0, "end")
        self.patient_data = []
        conn = get_connection()
        rows = conn.execute("SELECT id, name FROM patients WHERE status='入院中' ORDER BY name").fetchall()
        for r in rows:
            self.patient_list.insert("end", r["name"])
            self.patient_data.append(r)
        conn.close()

    def _setup_launch_screen(self):
        self.editor_root = ctk.CTkFrame(self, fg_color="transparent")
        self.editor_root.grid(row=0, column=1, sticky="nsew")
        
        self.msg = ctk.CTkLabel(self.editor_root, text="左のリストから患者を選択してください", font=(FONT_FAMILY[0], 16))
        self.msg.place(relx=0.5, rely=0.3, anchor="center")

        # The 'Real' UI: Excel itself
        self.launch_btn = ctk.CTkButton(self.editor_root, text="① 本物のExcelで編集・評価を開始", 
                                        width=400, height=80, font=(FONT_FAMILY[0], 18, "bold"),
                                        fg_color="#217346", hover_color="#1a5c38", # Excel Green
                                        command=self._launch_excel_editor)
        
        self.sync_btn = ctk.CTkButton(self.editor_root, text="② 編集内容をシステムに同期 (Sync)", 
                                        width=400, height=60, font=(FONT_FAMILY[0], 16, "bold"),
                                        fg_color=COLORS["success"], command=self._sync_from_excel)

        self.print_btn = ctk.CTkButton(self.editor_root, text="提出用Excelを出力 (印刷用)", 
                                        width=400, height=50, font=(FONT_FAMILY[0], 14),
                                        fg_color=COLORS["secondary"], command=self._export_excel)

    def _on_patient_selected(self, event):
        idx = self.patient_list.curselection()
        if not idx: return
        self.patient_id = self.patient_data[idx[0]]["id"]
        self.msg.configure(text=f"選択中: {self.patient_data[idx[0]]['name']} 様")
        self.launch_btn.place(relx=0.5, rely=0.45, anchor="center")
        self.sync_btn.place(relx=0.5, rely=0.58, anchor="center")
        self.print_btn.place(relx=0.5, rely=0.72, anchor="center")

    def _launch_excel_editor(self):
        if not self.patient_id: return
        conn = get_connection()
        plan = conn.execute("SELECT * FROM rehab_plans WHERE patient_id=? ORDER BY plan_date DESC LIMIT 1", (self.patient_id,)).fetchone()
        conn.close()
        
        data = dict(plan) if plan else {}
        try:
            path = prepare_editing_excel(self.patient_id, data)
            os.startfile(path)
            messagebox.showinfo("Excel起動", "本物のExcelが起動しました。\n入力を完了して『保存』してから、アプリの『同期』ボタンを押してください。")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _sync_from_excel(self):
        if not self.patient_id: return
        try:
            new_data = scrape_editing_excel(self.patient_id)
            if not new_data:
                 messagebox.showwarning("警告", "編集用ファイルが見つかりません。")
                 return
            
            # Save to DB
            conn = get_connection()
            new_data["patient_id"] = self.patient_id
            new_data["plan_date"] = datetime.now().strftime("%Y-%m-%d")
            
            # Filter keys existing in schema
            cols = ", ".join(new_data.keys())
            placeholders = ", ".join(["?"] * len(new_data))
            conn.execute(f"INSERT INTO rehab_plans ({cols}) VALUES ({placeholders})", list(new_data.values()))
            conn.commit()
            conn.close()
            
            messagebox.showinfo("同期完了", "Excelでの入力内容をデータベースに保存しました。")
        except Exception as e:
            messagebox.showerror("同期エラー", f"Excelがまだ開いているか、読み取りに失敗しました:\n{e}")

    def _export_excel(self):
        if not self.patient_id: return
        conn = get_connection()
        plan = conn.execute("SELECT * FROM rehab_plans WHERE patient_id=? ORDER BY plan_date DESC LIMIT 1", (self.patient_id,)).fetchone()
        p = conn.execute("SELECT name FROM patients WHERE id=?", (self.patient_id,)).fetchone()
        conn.close()
        
        data = dict(plan) if plan else {}
        data["patient_name"] = p["name"]
        
        try:
            path = export_to_excel(self.patient_id, data)
            webbrowser.open(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_patients(self):
        self.patient_list.delete(0, "end")
        self.patient_data = []
        conn = get_connection()
        rows = conn.execute("SELECT id, name FROM patients WHERE status='入院中' ORDER BY name").fetchall()
        for r in rows:
            self.patient_list.insert("end", r["name"])
            self.patient_data.append(r)
        conn.close()
