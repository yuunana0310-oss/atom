import customtkinter as ctk
from config import APP_TITLE, WINDOW_SIZE, CTK_APPEARANCE, CTK_THEME

ctk.set_appearance_mode(CTK_APPEARANCE)
ctk.set_default_color_theme(CTK_THEME)

TABS = [
    ("ホーム",       "views.home",              "HomeView"),
    ("患者一覧",     "views.patient_list",      "PatientListView"),
    ("訪問管理",     "views.visit_management",  "VisitManagementView"),
    ("業務日誌",     "views.daily_journal",     "DailyJournalView"),
    ("スタッフ管理", "views.staff_master",      "StaffMasterView"),
    ("担当医管理",   "views.doctor_master",     "DoctorMasterView"),
]


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self._build()

    def _build(self):
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.pack(fill="both", expand=True, padx=12, pady=12)

        for label, module_path, class_name in TABS:
            tab = self._tabs.add(label)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

            if module_path and class_name:
                import importlib
                mod = importlib.import_module(module_path)
                view_cls = getattr(mod, class_name)
                view_cls(tab).grid(row=0, column=0, sticky="nsew")
            else:
                ctk.CTkLabel(
                    tab,
                    text=f"「{label}」は Phase 2 以降で実装予定です",
                    font=ctk.CTkFont(size=14),
                    text_color="gray"
                ).grid(row=0, column=0)
