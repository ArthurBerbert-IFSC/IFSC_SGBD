from PyQt6.QtCore import QObject, pyqtSignal
from config.permission_templates import PERMISSION_TEMPLATES


class GroupsController(QObject):
    """Controller dedicado às operações de grupos e privilégios."""

    data_changed = pyqtSignal()

    def __init__(self, role_manager):
        super().__init__()
        self.role_manager = role_manager
        self._is_refreshing = False
        self._is_applying = False

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
        """Retorna privilégios futuros com informação de owner.

        Evita reentrância usando ``_is_refreshing`` para ignorar chamadas
        simultâneas.
        """
        if self._is_refreshing:
            return {}
        self._is_refreshing = True
        try:
            data = self.role_manager.dao.get_default_privileges(group_name, "r")
        except Exception:
            data = {}
        finally:
            self._is_refreshing = False

        meta = data.pop("_meta", {})
        owners = meta.get("owner_roles", {})
        result = {}
        for schema, grants in data.items():
            result[schema] = {
                "owner": owners.get(schema),
                "privileges": grants.get(group_name, set()),
            }
        return result

    def list_privilege_templates(self):
        return PERMISSION_TEMPLATES

    def apply_group_privileges(
        self,
        group_name: str,
        privileges,
        obj_type: str = "TABLE",
        defaults_applied: bool = False,
    ):
        success = self.role_manager.set_group_privileges(
            group_name,
            privileges,
            obj_type=obj_type,
            defaults_applied=defaults_applied,
        )
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
        """Aplica ``ALTER DEFAULT PRIVILEGES`` com trava de reentrância.

        Após aplicar, dispara ``data_changed`` para que a interface possa
        reconsultar o estado atualizado.
        """
        if self._is_applying:
            return False
        self._is_applying = True
        try:
            success = self.role_manager.alter_default_privileges(
                group_name, schema, obj_type, privileges
            )
            if success:
                # READ-BACK: reconsulta apenas os defaults do grupo/objeto-alvo
                code_map = {"tables": "r", "sequences": "S", "functions": "f", "types": "T"}
                code = code_map.get(obj_type, "r")
                try:
                    self.role_manager.dao.get_default_privileges(group_name, code)
                except Exception:
                    pass
                self.data_changed.emit()
            return success
        finally:
            self._is_applying = False

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
