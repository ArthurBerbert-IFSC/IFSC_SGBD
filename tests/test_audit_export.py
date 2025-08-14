import csv
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from gerenciador_postgres.gui.audit_view import AuditView


def test_export_logs_creates_csv(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    view = AuditView.__new__(AuditView)
    view.table_logs = QTableWidget()
    view.table_logs.setColumnCount(2)
    view.table_logs.setHorizontalHeaderLabels(["col1", "col2"])
    view.table_logs.setRowCount(1)
    view.table_logs.setItem(0, 0, QTableWidgetItem("a"))
    view.table_logs.setItem(0, 1, QTableWidgetItem("b"))

    dest = tmp_path / "logs.csv"
    monkeypatch.setattr(
        "gerenciador_postgres.gui.audit_view.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(dest), "csv"),
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.audit_view.QMessageBox.information",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.audit_view.QMessageBox.critical",
        lambda *a, **k: None,
    )

    view._export_logs()

    with open(dest, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert rows == [["col1", "col2"], ["a", "b"]]

