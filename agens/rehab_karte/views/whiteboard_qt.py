"""
ホワイトボード風 日次割り当て画面（PyQt6）
起動: python views/whiteboard_qt.py  （rehab_karte/ ディレクトリから）
"""
from __future__ import annotations
import json
import sys
import os

# rehab_karte/ をパスに追加（standalone起動用）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QFrame, QPushButton, QDateEdit, QSizePolicy,
    QSpacerItem,
)
from PyQt6.QtCore import (
    Qt, QMimeData, QDate, pyqtSignal, QPoint,
)
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QCursor

import models.assignment as assignment_model
import models.patient as patient_model
import models.staff as staff_model

MIME_TYPE = "application/x-patient-card"

ROLE_COLORS = {
    "PT": ("#E3F2FD", "#1565C0"),   # 薄青 / 濃青
    "OT": ("#E8F5E9", "#2E7D32"),   # 薄緑 / 濃緑
    "ST": ("#FFF3E0", "#E65100"),   # 薄橙 / 濃橙
    "その他": ("#F3E5F5", "#6A1B9A"),
}


# ─────────────────────────────────────────
#  患者カード
# ─────────────────────────────────────────

class PatientCard(QFrame):
    remove_requested = pyqtSignal(int)   # assignment_id

    def __init__(
        self,
        patient: dict,
        assignment_id: int | None = None,
        show_remove: bool = False,
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.patient_id   = patient["id"]
        self.patient_name = patient["name"]
        self.assignment_id = assignment_id
        self._drag_start: QPoint | None = None

        height = 30 if compact else 44
        self.setFixedHeight(height)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._apply_style(False)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)

        ward = patient.get("ward") or ""
        detail = f" [{ward}]" if ward else ""
        font_size = 9 if compact else 11
        self._name_lbl = QLabel(f"{self.patient_name}{detail}")
        self._name_lbl.setFont(QFont("", font_size))
        layout.addWidget(self._name_lbl)
        layout.addStretch()

        if show_remove and assignment_id is not None:
            btn = QPushButton("×")
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(
                "QPushButton { color:#E57373; font-weight:bold; border:none; }"
                "QPushButton:hover { color:#C62828; }"
            )
            btn.clicked.connect(lambda: self.remove_requested.emit(self.assignment_id))
            layout.addWidget(btn)

    def _apply_style(self, hover: bool):
        bg = "#E3F2FD" if hover else "white"
        border = "#2196F3" if hover else "#CCCCCC"
        self.setStyleSheet(
            f"PatientCard {{ background:{bg}; border:1px solid {border};"
            f" border-radius:6px; }}"
        )

    def enterEvent(self, _):  self._apply_style(True)
    def leaveEvent(self, _):  self._apply_style(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        payload = json.dumps({
            "patient_id":    self.patient_id,
            "patient_name":  self.patient_name,
            "assignment_id": self.assignment_id,
        })
        mime.setData(MIME_TYPE, payload.encode())
        drag.setMimeData(mime)

        # ドラッグ中のサムネイル
        px = QPixmap(self.size())
        painter = QPainter(px)
        painter.setOpacity(0.85)
        self.render(painter)
        painter.end()
        drag.setPixmap(px)
        drag.setHotSpot(event.pos())

        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)


# ─────────────────────────────────────────
#  未割り当てパネル（左）
# ─────────────────────────────────────────

class UnassignedPanel(QFrame):
    """全患者を表示するソースリスト。ドロップで「未割り当てに戻す」"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._patients: list[dict] = []
        self.setAcceptDrops(True)
        self.setMinimumWidth(200)
        self.setMaximumWidth(240)
        self.setStyleSheet("UnassignedPanel { background:#F5F5F5; border-right:2px solid #DDDDDD; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        hdr = QLabel("患者一覧")
        hdr.setFont(QFont("", 13, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

    def load(self, patients: list[dict]):
        self._patients = patients
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for p in patients:
            card = PatientCard(p, compact=True)
            self._layout.insertWidget(self._layout.count() - 1, card)

    # ── ドロップ受け入れ（割り当て済みカードを戻す） ──

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        """割り当て済みカードをドロップ → 削除シグナルを親に伝える"""
        if not event.mimeData().hasFormat(MIME_TYPE):
            return
        data = json.loads(event.mimeData().data(MIME_TYPE).data())
        assignment_id = data.get("assignment_id")
        if assignment_id is not None:
            assignment_model.delete(assignment_id)
        event.acceptProposedAction()
        # 親（WhiteboardWindow）にリフレッシュを依頼
        win = self.window()
        if hasattr(win, "refresh"):
            win.refresh()


# ─────────────────────────────────────────
#  セラピストカラム（右）
# ─────────────────────────────────────────

class TherapistColumn(QFrame):
    def __init__(self, therapist: dict, visit_date: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.therapist  = therapist
        self.visit_date = visit_date
        self.setAcceptDrops(True)
        self.setMinimumWidth(200)

        bg, border = ROLE_COLORS.get(therapist["role"], ("#FAFAFA", "#888888"))
        self.setStyleSheet(
            f"TherapistColumn {{ background:white; border:2px solid {border};"
            f" border-radius:8px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ヘッダ
        hdr = QFrame()
        hdr.setStyleSheet(f"background:{bg}; border-radius:4px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(8, 6, 8, 6)
        role_lbl = QLabel(therapist["role"])
        role_lbl.setFont(QFont("", 10))
        role_lbl.setStyleSheet(f"color:{border}; font-weight:bold;")
        name_lbl = QLabel(therapist["name"])
        name_lbl.setFont(QFont("", 12, QFont.Weight.Bold))
        hdr_layout.addWidget(role_lbl)
        hdr_layout.addWidget(name_lbl)
        root.addWidget(hdr)

        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._card_layout = QVBoxLayout(self._inner)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(4)
        self._card_layout.addStretch()
        scroll.setWidget(self._inner)
        root.addWidget(scroll)

        # ドロップヒント
        self._hint = QLabel("ここにドロップ")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color:#AAAAAA; font-size:12px;")
        root.addWidget(self._hint)

    def load(self, assignments: list[dict]):
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._hint.setVisible(len(assignments) == 0)

        for a in assignments:
            patient = {
                "id":     a["patient_id"],
                "name":   a["patient_name"],
                "ward":   a.get("ward", ""),
                "status": a.get("patient_status", ""),
            }
            card = PatientCard(patient, assignment_id=a["id"], show_remove=True)
            card.remove_requested.connect(self._on_remove)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def _on_remove(self, assignment_id: int):
        assignment_model.delete(assignment_id)
        win = self.window()
        if hasattr(win, "refresh"):
            win.refresh()

    # ── ドロップ ──

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            self.setStyleSheet(self.styleSheet().replace("white", "#FFFDE7"))
            event.acceptProposedAction()

    def dragLeaveEvent(self, _):
        self.setStyleSheet(self.styleSheet().replace("#FFFDE7", "white"))

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("#FFFDE7", "white"))
        if not event.mimeData().hasFormat(MIME_TYPE):
            return

        data = json.loads(event.mimeData().data(MIME_TYPE).data())
        patient_id = data["patient_id"]
        therapist_id = self.therapist["id"]

        if not assignment_model.exists(self.visit_date, patient_id, therapist_id):
            order = assignment_model.get_max_order(self.visit_date, therapist_id) + 1
            assignment_model.create(self.visit_date, patient_id, therapist_id, order)

        event.acceptProposedAction()
        win = self.window()
        if hasattr(win, "refresh"):
            win.refresh()


# ─────────────────────────────────────────
#  メインウィンドウ
# ─────────────────────────────────────────

class WhiteboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ホワイトボード — 日次割り当て")
        self.resize(1200, 700)
        self._visit_date = date.today().isoformat()
        self._build()
        self.refresh()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ── ツールバー ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        lbl = QLabel("対象日：")
        lbl.setFont(QFont("", 11))
        toolbar.addWidget(lbl)

        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("yyyy/MM/dd")
        self._date_edit.setFont(QFont("", 11))
        self._date_edit.setFixedHeight(32)
        self._date_edit.dateChanged.connect(self._on_date_changed)
        toolbar.addWidget(self._date_edit)

        btn_today = QPushButton("今日")
        btn_today.setFixedHeight(32)
        btn_today.clicked.connect(self._go_today)
        toolbar.addWidget(btn_today)

        toolbar.addStretch()

        btn_refresh = QPushButton("更新")
        btn_refresh.setFixedHeight(32)
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(btn_refresh)

        main_layout.addLayout(toolbar)

        # ── 本体（左：未割り当て ／ 右：セラピスト列） ──
        body = QHBoxLayout()
        body.setSpacing(12)

        self._unassigned = UnassignedPanel()
        body.addWidget(self._unassigned)

        # セラピスト列スクロールエリア
        self._col_scroll = QScrollArea()
        self._col_scroll.setWidgetResizable(True)
        self._col_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._col_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._col_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cols_widget = QWidget()
        self._cols_layout = QHBoxLayout(self._cols_widget)
        self._cols_layout.setContentsMargins(0, 0, 0, 0)
        self._cols_layout.setSpacing(10)
        self._col_scroll.setWidget(self._cols_widget)

        body.addWidget(self._col_scroll, stretch=1)
        main_layout.addLayout(body)

    def _on_date_changed(self, qdate: QDate):
        self._visit_date = qdate.toString("yyyy-MM-dd")
        self.refresh()

    def _go_today(self):
        self._date_edit.setDate(QDate.currentDate())

    def refresh(self):
        visit_date = self._visit_date

        # ── 患者一覧（入院中のみ・未割り当てのみ） ──
        all_inpatients = [
            p for p in patient_model.get_all()
            if p["status"] == "入院中"
        ]
        assignments = assignment_model.get_by_date(visit_date)
        assigned_ids = {a["patient_id"] for a in assignments}
        unassigned = [p for p in all_inpatients if p["id"] not in assigned_ids]
        self._unassigned.load(unassigned)

        # ── セラピスト列を再描画 ──
        # 既存列を削除
        while self._cols_layout.count():
            item = self._cols_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        therapists = staff_model.get_all(active_only=True)
        if not therapists:
            lbl = QLabel("スタッフが登録されていません\n（スタッフ管理タブで追加してください）")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#AAAAAA;")
            self._cols_layout.addWidget(lbl)
        else:
            # assignments は上で取得済み
            by_therapist: dict[int, list[dict]] = {}
            for a in assignments:
                by_therapist.setdefault(a["therapist_id"], []).append(a)

            for t in therapists:
                col = TherapistColumn(t, visit_date)
                col.load(by_therapist.get(t["id"], []))
                self._cols_layout.addWidget(col)

            self._cols_layout.addStretch()


# ─────────────────────────────────────────
#  エントリポイント
# ─────────────────────────────────────────

def run_whiteboard():
    """customtkinter アプリから subprocess で起動する場合も使用"""
    app = QApplication.instance() or QApplication(sys.argv)
    win = WhiteboardWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    run_whiteboard()
