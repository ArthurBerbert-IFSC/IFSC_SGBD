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

    def get_schema_level_privileges(self, group_name: str):
        try:
            return self.role_manager.dao.get_schema_privileges(group_name)
        except Exception:
            return {}

    def get_default_table_privileges(self, group_name: str):
        try:
            return self.role_manager.dao.get_default_table_privileges(group_name)
        except Exception:
            return {}

    def list_privilege_templates(self):
        return PERMISSION_TEMPLATES

    def apply_group_privileges(self, group_name: str, privileges, obj_type: str = "TABLE"):
        success = self.role_manager.set_group_privileges(group_name, privileges, obj_type=obj_type)
        if success:
            # Sincroniza defaults para refletir os privilégios aplicados
            try:
                self.role_manager.sweep_privileges(target_group=group_name)
            except Exception:
                pass
            self.data_changed.emit()
        return success

    def apply_template_to_group(self, group_name: str, template: str):
        success = self.role_manager.apply_template_to_group(group_name, template)
        if success:
            try:
                self.role_manager.sweep_privileges(target_group=group_name)
            except Exception:
                pass
            self.data_changed.emit()
        return success

    def grant_database_privileges(self, group_name: str, privileges):
        success = self.role_manager.grant_database_privileges(group_name, privileges)
        if success:
            self.data_changed.emit()
        return success

    def grant_schema_privileges(self, group_name: str, schema: str, privileges):
        success = self.role_manager.grant_schema_privileges(group_name, schema, privileges)
        if success:
            try:
                self.role_manager.sweep_privileges(target_group=group_name)
            except Exception:
                pass
            self.data_changed.emit()
        return success

    def alter_default_privileges(self, group_name: str, schema: str, obj_type: str, privileges):
        success = self.role_manager.alter_default_privileges(group_name, schema, obj_type, privileges)
        if success:
            try:
                self.role_manager.sweep_privileges(target_group=group_name)
            except Exception:
                pass
            self.data_changed.emit()
        return success

    def get_current_database(self):
        return self.role_manager.dao.conn.get_dsn_parameters().get("dbname")

    # ---------------------------------------------------------------
    # Sincronização (sweep) de privilégios
    # ---------------------------------------------------------------
    def sweep_group_privileges(self, group_name: str) -> bool:
        """Reaplica GRANTs e ajusta default privileges para o grupo informado."""
        success = self.role_manager.sweep_privileges(target_group=group_name)
        if success:
            self.data_changed.emit()
        return success
