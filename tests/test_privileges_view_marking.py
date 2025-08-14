import os
import sys
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, Qt

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from gerenciador_postgres.gui.privileges_view import PrivilegesView


class DummyController(QObject):
    data_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

    def list_entities(self):
        return ["role1"], []

    def get_schema_tables(self, **kwargs):
        return {"public": ["t1"]}

    def get_group_privileges(self, role):
        return {"public": {"t1": {"SELECT"}}}

    def get_database_privileges(self, role):
        return {"CONNECT"}

    def get_schema_privileges(self, role):
        return {"public": {"USAGE"}}

    def apply_template_to_group(self, *args, **kwargs):
        return True

    def grant_database_privileges(self, *args, **kwargs):
        return True

    def grant_schema_privileges(self, *args, **kwargs):
        return True

    def apply_group_privileges(self, *args, **kwargs):
        return True

    def get_current_database(self):
        return "testdb"


def test_populate_tree_marks_privileges():
    app = QApplication.instance() or QApplication([])
    controller = DummyController()
    view = PrivilegesView(controller=controller)
    db_item = view.treeDbPrivileges.topLevelItem(0)
    assert db_item.checkState(1) == Qt.CheckState.Checked
    assert db_item.checkState(2) == Qt.CheckState.Unchecked
    schema_item = view.treeSchemaPrivileges.topLevelItem(0)
    assert schema_item.checkState(1) == Qt.CheckState.Checked
    table_schema_item = view.treeTablePrivileges.topLevelItem(0)
    table_item = table_schema_item.child(0)
    assert table_item.checkState(1) == Qt.CheckState.Checked
    view.close()
