import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import initialize_db
from views.main_window import MainWindow

if __name__ == "__main__":
    initialize_db()
    app = MainWindow()
    app.mainloop()
