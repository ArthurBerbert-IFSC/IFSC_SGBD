from PyQt6.QtCore import QObject, pyqtSignal
from config.permission_templates import PERMISSION_TEMPLATES


class UsersController(QObject):
    """Controller que orquestra operações de usuário e grupo."""

    data_changed = pyqtSignal()

    def __init__(self, role_manager):
        super().__init__()
        self.role_manager = role_manager

    def list_entities(self):
        users = self.role_manager.list_users()
        groups = self.role_manager.list_groups()
        return users, groups

    def create_user(self, username: str, password: str):
        result = self.role_manager.create_user(username, password)
        self.data_changed.emit()
        return result

    def create_group(self, group_name: str):
        result = self.role_manager.create_group(group_name)
        self.data_changed.emit()
        return result

    def list_groups(self):
        """Retorna lista de grupos existentes."""
        return self.role_manager.list_groups()

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Associa um usuário a um grupo."""
        success = self.role_manager.add_user_to_group(username, group_name)
        if success:
            self.data_changed.emit()
        return success

    def delete_user(self, username: str) -> bool:
        success = self.role_manager.delete_user(username)
        if success:
            self.data_changed.emit()
        return success

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

    def change_password(self, username: str, new_password: str) -> bool:
        return self.role_manager.change_password(username, new_password)

    # --- Métodos de turmas ----------------------------------------------

    def list_groups(self):
        return self.role_manager.list_groups()

    def list_user_groups(self, username: str):
        return self.role_manager.list_user_groups(username)

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        success = self.role_manager.add_user_to_group(username, group_name)
        if success:
            self.data_changed.emit()
        return success

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        success = self.role_manager.remove_user_from_group(username, group_name)
        if success:
            self.data_changed.emit()
        return success

    # --- Novos métodos de privilégios ----------------------------------

    def get_schema_tables(self):
        """Retorna dicionário de schemas e suas tabelas."""
        return self.role_manager.list_tables_by_schema()

    def list_privilege_templates(self):
        """Templates simples de conjunto de permissões."""
        return PERMISSION_TEMPLATES

    def apply_group_privileges(self, group_name: str, privileges):
        """Encaminha atualização de privilégios ao RoleManager."""
        success = self.role_manager.set_group_privileges(group_name, privileges)
        if success:
            self.data_changed.emit()
        return success

    def apply_template_to_group(self, group_name: str, template: str):
        """Aplica um template de permissões diretamente a um grupo."""
        success = self.role_manager.apply_template_to_group(group_name, template)
        if success:
            self.data_changed.emit()
        return success

