from PyQt6.QtCore import QObject, pyqtSignal
from config.permission_templates import PERMISSION_TEMPLATES


class GroupsController(QObject):
    """Controller dedicado às operações de grupos e privilégios."""

    data_changed = pyqtSignal()

    def __init__(self, role_manager):
        super().__init__()
        self.role_manager = role_manager

    # ---------------------------------------------------------------
    # Operações de grupos
    # ---------------------------------------------------------------
    def list_groups(self):
        return self.role_manager.list_groups()

    def create_group(self, group_name: str):
        result = self.role_manager.create_group(group_name)
        self.data_changed.emit()
        return result

    def delete_group(self, group_name: str) -> bool:
        success = self.role_manager.delete_group(group_name)
        if success:
            self.data_changed.emit()
        return success

    def delete_group_and_members(self, group_name: str) -> bool:
        success = self.role_manager.delete_group_and_members(group_name)
        if success:
            self.data_changed.emit()
        return success

    def list_group_members(self, group_name: str):
        return self.role_manager.list_group_members(group_name)

    # ---------------------------------------------------------------
    # Operações de privilégios
    # ---------------------------------------------------------------
    def get_schema_tables(self, **kwargs):
        return self.role_manager.list_tables_by_schema(**kwargs)

    def get_group_privileges(self, group_name: str):
        return self.role_manager.get_group_privileges(group_name)

    def list_privilege_templates(self):
        return PERMISSION_TEMPLATES

    def apply_group_privileges(self, group_name: str, privileges):
        success = self.role_manager.set_group_privileges(group_name, privileges)
        if success:
            self.data_changed.emit()
        return success

    def apply_template_to_group(self, group_name: str, template: str):
        success = self.role_manager.apply_template_to_group(group_name, template)
        if success:
            self.data_changed.emit()
        return success
