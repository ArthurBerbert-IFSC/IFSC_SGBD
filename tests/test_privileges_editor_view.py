import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gerenciador_postgres.gui import PrivilegesEditorView


class DummyExecutor:
    def __init__(self):
        self.ops = None

    def apply(self, ops):
        self.ops = ops


def test_generate_and_apply():
    app = QApplication.instance() or QApplication([])
    executor = DummyExecutor()
    view = PrivilegesEditorView(executor=executor)
    view.set_creators(["alice"])

    item = view.treeCreators.topLevelItem(0)
    item.setCheckState(1, Qt.CheckState.Checked)

    view.btnGenerate.click()

    expected = {
        "action": "ALTER DEFAULT PRIVILEGES",
        "badge": "ALTER DEFAULT PRIVILEGES",
        "target": "TABLES",
        "schema": "public",
        "privileges": ["ALL"],
        "grantee": "alice",
    }
    assert view._operations == [expected]
    html = view.txtPreview.toHtml()
    assert "[ALTER DEFAULT PRIVILEGES]" in html
    assert (
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO alice;"
        in html
    )
    assert view.tabs.currentWidget() is view.txtPreview

    view.btnApply.click()
    assert executor.ops == [expected]
