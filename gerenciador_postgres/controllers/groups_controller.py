from PyQt6.QtCore import QObject, pyqtSignal
from config.permission_templates import PERMISSION_TEMPLATES
from gerenciador_postgres.controllers.users_controller import UsersController


class DependencyWarning(RuntimeError):
    """Sinaliza que a operação requer REVOKE ... CASCADE."""


class GroupsController(QObject):
    """Controller dedicado às operações de grupos, usuários e privilégios."""

    data_changed = pyqtSignal()
    members_changed = pyqtSignal(str)

    def __init__(self, role_manager):
        super().__init__()
        self.role_manager = role_manager
        self._is_refreshing = False
        self._is_applying = False
        # Controller auxiliar para operações de usuário
        self._user_ctrl = UsersController(role_manager)
        self._user_ctrl.data_changed.connect(self.data_changed)

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
    # Operações de usuário (delegadas)
    # ---------------------------------------------------------------
    def list_users(self):
        return self._user_ctrl.list_users()

    def create_user(self, username: str, password: str, valid_until: str | None = None):
        return self._user_ctrl.create_user(username, password, valid_until)

    def get_user(self, username: str):
        return self._user_ctrl.get_user(username)

    def create_users_batch(
        self,
        users_data: list,
        valid_until: str | None = None,
        group_name: str | None = None,
        renew: bool = False,
    ):
        return self._user_ctrl.create_users_batch(users_data, valid_until, group_name, renew)

    def renew_user_validity(self, username: str, new_date: str) -> bool:
        return self._user_ctrl.renew_user_validity(username, new_date)

    def delete_user(self, username: str) -> bool:
        return self._user_ctrl.delete_user(username)

    def change_password(self, username: str, password: str) -> bool:
        return self._user_ctrl.change_password(username, password)

    def list_user_groups(self, username: str):
        return self._user_ctrl.list_user_groups(username)


    def add_user_to_group(
        self,
        username: str,
        group_name: str,
        auto_apply_defaults: bool = True,
    ) -> bool:
        success = self.role_manager.add_user_to_group(username, group_name)
        if success:
            self.members_changed.emit(group_name)
            if auto_apply_defaults:
                try:
                    self.apply_defaults_to_user(username)
                except Exception:
                    pass
        return success

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        success = self.role_manager.remove_user_from_group(username, group_name)
        if success:
            self.members_changed.emit(group_name)
        return success

    def transfer_user_group(self, username: str, old_group: str, new_group: str) -> bool:
        success = self.role_manager.transfer_user_group(username, old_group, new_group)
        if success:
            self.members_changed.emit(old_group)
            self.members_changed.emit(new_group)
        return success

    def apply_defaults_to_user(self, username: str) -> bool:
        """Reaplica os ``ALTER DEFAULT PRIVILEGES`` existentes ao usuário."""
        try:
            data = self.role_manager.dao.get_default_privileges(objtype="r")
        except Exception:
            return False

        user_groups = set()
        try:
            user_groups = set(self.list_user_groups(username))
        except Exception:
            pass

        meta = data.pop("_meta", {})
        owners = meta.get("owner_roles", {})
        applied = False
        for schema, grants in data.items():
            owner = owners.get(schema)
            privs: set = set()
            for grp in user_groups:
                privs |= grants.get(grp, set())
            if privs:
                try:
                    self.alter_default_privileges(
                        username,
                        schema,
                        "tables",
                        privs,
                        owner=owner,
                        emit_signal=False,
                    )
                    applied = True
                except Exception:
                    continue
        if applied:
            self.data_changed.emit()
        return applied

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
            data = self.role_manager.dao.get_default_privileges(objtype="r")
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
        emit_signal: bool = True,
        check_dependencies: bool = True,
    ):
        try:
            success = self.role_manager.set_group_privileges(
                group_name,
                privileges,
                obj_type=obj_type,
                defaults_applied=defaults_applied,
                check_dependencies=check_dependencies,
            )
        except Exception as e:
            if "[WARN-DEPEND]" in str(e):
                raise DependencyWarning(str(e))
            raise
        if success and emit_signal:
            self.data_changed.emit()
        return success

    def apply_template_to_group(self, group_name: str, template: str):
        success = self.role_manager.apply_template_to_group(group_name, template)
        if success:
            self.data_changed.emit()
        return success

    def grant_database_privileges(self, group_name: str, privileges):
        try:
            success = self.role_manager.grant_database_privileges(group_name, privileges)
        except Exception as e:
            if "[WARN-DEPEND]" in str(e):
                raise DependencyWarning(str(e))
            raise
        if success:
            self.data_changed.emit()
        return success

    def grant_schema_privileges(
        self,
        group_name: str,
        schema: str,
        privileges,
        emit_signal: bool = True,
    ):
        try:
            success = self.role_manager.grant_schema_privileges(group_name, schema, privileges)
        except Exception as e:
            if "[WARN-DEPEND]" in str(e):
                raise DependencyWarning(str(e))
            raise
        if success and emit_signal:
            self.data_changed.emit()
        return success

    def alter_default_privileges(
        self,
        group_name: str,
        schema: str,
        obj_type: str,
        privileges,
        owner: str | None = None,
    emit_signal: bool = True,
    ):
        """Aplica ``ALTER DEFAULT PRIVILEGES`` com trava de reentrância.

        Após aplicar, dispara ``data_changed`` para que a interface possa
        reconsultar o estado atualizado.
        """
        if self._is_applying:
            return False
        self._is_applying = True
        try:
            kwargs = {"for_role": owner} if owner else {}
            try:
                success = self.role_manager.alter_default_privileges(
                    group_name, schema, obj_type, privileges, **kwargs
                )
            except Exception as e:
                if "[WARN-DEPEND]" in str(e):
                    raise DependencyWarning(str(e))
                raise
            if success:
                # READ-BACK: reconsulta apenas os defaults do grupo/objeto-alvo
                code_map = {"tables": "r", "sequences": "S", "functions": "f", "types": "T"}
                code = code_map.get(obj_type, "r")
                try:
                    self.role_manager.dao.get_default_privileges(owner=owner, objtype=code)
                except Exception:
                    pass
                if emit_signal:
                    self.data_changed.emit()
            return success
        finally:
            self._is_applying = False

    def get_current_database(self):
        return self.role_manager.dao.conn.get_dsn_parameters().get("dbname")
