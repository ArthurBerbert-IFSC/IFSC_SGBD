import os
import sys
from types import SimpleNamespace
from PyQt6.QtWidgets import QMessageBox

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gerenciador_postgres.gui.connection_dialog import ConnectionDialog


def _make_dialog():
    dlg = ConnectionDialog.__new__(ConnectionDialog)
    dlg.chkSavePassword = SimpleNamespace(isChecked=lambda: True)
    dlg.txtPassword = SimpleNamespace(text=lambda: "p")
    dlg.txtUser = SimpleNamespace(text=lambda: "u")
    dlg.cmbProfiles = SimpleNamespace(currentText=lambda: "")
    dlg.update_password_indicator = lambda: None
    dlg._keyring_warning_shown = False
    return dlg


def test_set_password_called(monkeypatch):
    dlg = _make_dialog()

    called = {}

    def fake_set(service, user, pwd):
        called["args"] = (service, user, pwd)

    monkeypatch.setattr(
        "gerenciador_postgres.gui.connection_dialog.keyring.set_password", fake_set
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.connection_dialog.QMessageBox.information",
        lambda *a, **k: None,
    )

    dlg._maybe_save_password()
    assert called["args"] == ("IFSC_SGBD", "u", "p")


def test_delete_password_called(monkeypatch):
    dlg = _make_dialog()

    monkeypatch.setattr(
        "gerenciador_postgres.gui.connection_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "gerenciador_postgres.gui.connection_dialog.QMessageBox.information",
        lambda *a, **k: None,
    )
    deleted = {}

    def fake_delete(service, user):
        deleted["args"] = (service, user)

    monkeypatch.setattr(
        "gerenciador_postgres.gui.connection_dialog.keyring.delete_password", fake_delete
    )

    dlg.delete_saved_password()
    assert deleted["args"] == ("IFSC_SGBD", "u")


def test_accept_triggers_save(monkeypatch):
    dlg = _make_dialog()

    called = {}

    def fake_save():
        called["called"] = True

    dlg._maybe_save_password = fake_save
    monkeypatch.setattr("PyQt6.QtWidgets.QDialog.accept", lambda self: None)

    ConnectionDialog.accept(dlg)
    assert called.get("called")
