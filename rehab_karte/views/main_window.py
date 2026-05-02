import customtkinter as ctk
import importlib
from config import APP_TITLE, WINDOW_SIZE, CTK_APPEARANCE, CTK_THEME, COLORS, FONT_FAMILY

ctk.set_appearance_mode(CTK_APPEARANCE)
ctk.set_default_color_theme(CTK_THEME)

# (ラベル, モジュールパス, クラス名, アイコン)
NAV_ITEMS = [
    ("ホーム",       "views.home",              "HomeView",         "🏠"),
    ("患者一覧",     "views.patient_list",      "PatientListView",  "👥"),
    ("リハ計画書",   "views.plan_editor",       "PlanEditorView",   "📝"),
    ("訪問管理",     "views.visit_management",  "VisitManagementView", "📅"),
    ("業務日誌",     "views.daily_journal",     "DailyJournalView", "📝"),
    ("スタッフ管理", "views.staff_master",      "StaffMasterView",  "👩‍⚕️"),
    ("担当医管理",   "views.doctor_master",     "DoctorMasterView", "🏥"),
]


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.configure(fg_color=COLORS["bg_light"])
        
        self._current_view = None
        self._nav_buttons = {}
        self._build()
        self._select_view("ホーム")

    def _build(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- サイドバー ----
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS["primary"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(len(NAV_ITEMS) + 2, weight=1)

        logo = ctk.CTkLabel(sidebar, text="REHAB KARTE", 
                            font=ctk.CTkFont(family=FONT_FAMILY[0], size=22, weight="bold"),
                            text_color="white")
        logo.grid(row=0, column=0, padx=20, pady=(30, 40))

        for i, (label, mod, cls, icon) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}  {label}",
                height=45, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY[0], size=14, weight="bold"),
                fg_color="transparent", text_color="#CBD5E1",
                anchor="w", hover_color=COLORS["secondary"],
                command=lambda l=label: self._select_view(l)
            )
            btn.grid(row=i+1, column=0, padx=12, pady=4, sticky="ew")
            self._nav_buttons[label] = btn

        # ---- コンテンツエリア ----
        self._container = ctk.CTkFrame(self, corner_radius=20, fg_color=COLORS["bg_light"])
        self._container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._container.grid_columnconfigure(0, weight=1)
        self._container.grid_rowconfigure(0, weight=1)

    def _select_view(self, label: str):
        # ボタンの強調表示
        for l, btn in self._nav_buttons.items():
            if l == label:
                btn.configure(fg_color=COLORS["accent"], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#CBD5E1")

        # ビューの入れ替え
        if self._current_view:
            self._current_view.destroy()

        item = next(x for x in NAV_ITEMS if x[0] == label)
        _, module_path, class_name, _ = item

        try:
            mod = importlib.import_module(module_path)
            view_cls = getattr(mod, class_name)
            self._current_view = view_cls(self._container)
            self._current_view.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            self._current_view = ctk.CTkLabel(
                self._container, 
                text=f"エラーが発生しました:\n{e}",
                font=ctk.CTkFont(size=14), text_color=COLORS["danger"]
            )
            self._current_view.grid(row=0, column=0)
