from PyQt6.QtCore import QObject, pyqtSignal


class UsersController(QObject):
    """Controller responsável pelas operações de usuário.

    Este controller orquestra chamadas de criação/atualização/exclusão de
    usuários e gerencia ações correlatas após operações em lote.
    """

    data_changed = pyqtSignal()

    def __init__(self, role_manager):
        super().__init__()
        self.role_manager = role_manager

    # ------------------------------------------------------------------
    # Operações de usuário
    # ------------------------------------------------------------------
    def list_users(self):
        return self.role_manager.list_users()

    def create_user(self, username: str, password: str, valid_until: str | None = None):
        result = self.role_manager.create_user(username, password, valid_until)
        self.data_changed.emit()
        return result

    def get_user(self, username: str):
        return self.role_manager.get_user(username)

    def create_users_batch(
        self,
        users_data: list,
        valid_until: str | None = None,
        group_name: str | None = None,
        renew: bool = False,
    ):
        """Cria múltiplos usuários de uma vez.

        Parameters
        ----------
        users_data: list
            Lista de tuplas ``(matricula, nome_completo)``.
        valid_until: str | None
            Data de expiração a ser aplicada a todos os usuários ou ``None``.
        group_name: str | None
            Turma à qual os usuários serão adicionados ou ``None``.
        """

        results = self.role_manager.create_users_batch(
            users_data, valid_until, group_name, renew
        )
        self.data_changed.emit()
        return results

    def renew_user_validity(self, username: str, new_date: str) -> bool:
        success = self.role_manager.renew_user_validity(username, new_date)
        if success:
            self.data_changed.emit()
        return success

    def delete_user(self, username: str) -> bool:
        success = self.role_manager.delete_user(username)
        if success:
            self.data_changed.emit()
        return success

    def delete_user_cascade_objects(self, username: str) -> bool:
        success = self.role_manager.delete_user_cascade_objects(username)
        if success:
            self.data_changed.emit()
        return success

    def user_has_owned_objects(self, username: str) -> bool:
        return self.role_manager.user_has_owned_objects(username)

    def change_password(self, username: str, password: str) -> bool:
        return self.role_manager.change_password(username, password)

    # ------------------------------------------------------------------
    # Operações relativas a grupos para um usuário
    # ------------------------------------------------------------------
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

    def list_user_groups(self, username: str):
        return self.role_manager.list_user_groups(username)

    def add_user_to_group(self, username: str, group_name: str) -> bool:
            """Adiciona usuário a um grupo sem emitir data_changed (preserva seleção na UI)."""
            return self.role_manager.add_user_to_group(username, group_name)

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
            """Remove usuário de um grupo sem emitir data_changed."""
            return self.role_manager.remove_user_from_group(username, group_name)

    def transfer_user_group(self, username: str, old_group: str, new_group: str) -> bool:
            """Transfere usuário de old_group para new_group (remove + adiciona)."""
            return self.role_manager.transfer_user_group(username, old_group, new_group)

    # --------------------------------------------------------------
    # Compat: algumas views podem chamar flush(); aqui não há buffer,
    # as operações já comitam imediatamente. Mantemos no-op.
    def flush(self):
        return None

