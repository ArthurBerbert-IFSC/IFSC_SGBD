from .db_manager import DBManager
from .data_models import User, Group
from typing import Optional, List, Dict, Set
import logging
import unicodedata
from psycopg2 import sql
from .config_manager import load_config

class RoleManager:
    """Camada de serviço: orquestra operações, valida regras e controla transações."""
    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema', audit_manager=None):
        self.dao = dao
        self.logger = logger
        self.operador = operador
        self.audit_manager = audit_manager

    def create_user(self, username: str, password: str, valid_until: str | None = None) -> str:
        dados_antes = None
        dados_depois = None
        sucesso = False

        try:
            if self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' já existe.")
            with self.dao.transaction():
                self.dao.insert_user(username, password, valid_until)

                dados_depois = {
                    'username': username,
                    'can_login': True,
                    'valid_until': valid_until,
                }
                sucesso = True

                if self.audit_manager:
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='CREATE_USER',
                        objeto_tipo='USER',
                        objeto_nome=username,
                        detalhes={'password_set': True, 'valid_until': valid_until},
                        dados_antes=dados_antes,
                        dados_depois=dados_depois,
                        sucesso=sucesso
                    )

            self.logger.info(f"[{self.operador}] Criou usuário: {username}")

            return username
            
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao criar usuário '{username}': {e}")
            
            # Registrar falha na auditoria
            if self.audit_manager:
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='CREATE_USER',
                        objeto_tipo='USER',
                        objeto_nome=username,
                        detalhes={'error': str(e)},
                        dados_antes=dados_antes,
                        dados_depois=dados_depois,
                        sucesso=False
                    )
            
            raise

    def create_users_batch(
        self,
        users_info: list,
        valid_until: str | None = None,
        group_name: str | None = None,
        renew: bool = False,
    ):
        """Cria múltiplos usuários gerando usernames a partir do nome completo.

        Parameters
        ----------
        users_info : list
            Lista de tuplas ``(matricula, nome_completo)``.
        valid_until : str | None
            Data de expiração opcional aplicada a todos os usuários.
        group_name : str | None
            Turma à qual os usuários serão adicionados.
        renew : bool
            Se ``True``, usuários já existentes terão sua validade
            atualizada para ``valid_until`` ao invés de gerar um novo
            username.
        """

        if group_name:
            try:
                if group_name not in self.list_groups():
                    self.create_group(group_name)
            except Exception as e:
                self.logger.error(
                    f"[{self.operador}] Falha ao garantir existência da turma '{group_name}': {e}"
                )
                raise

        created: List[str] = []
        for matricula, nome_completo in users_info:
            password = matricula
            nome_normalizado = unicodedata.normalize('NFKD', nome_completo)
            nome_ascii = nome_normalizado.encode('ascii', 'ignore').decode('ascii')
            partes = nome_ascii.strip().split()
            if not partes:
                continue
            first = partes[0].lower()
            last = partes[-1].lower() if len(partes) > 1 else ""
            tentativa = 0
            while True:
                if tentativa == 0:
                    username = first
                elif tentativa == 1:
                    username = f"{first}.{last}" if last else first
                else:
                    username = f"{first}.{last}{tentativa}" if last else f"{first}{tentativa}"
                # Checagem prévia para evitar exceção de duplicidade e acelerar a próxima tentativa
                try:
                    user_exists = self.dao.find_user_by_name(username)
                    if user_exists:
                        if renew:
                            success = self.update_user(username, valid_until=valid_until)
                            created_username = username if success else None
                            error = None if success else Exception(
                                f"Falha ao renovar usuário existente '{username}'"
                            )
                        else:
                            tentativa += 1
                            if tentativa > 100:
                                self.logger.error(
                                    f"[{self.operador}] Muitas tentativas para gerar username baseado em '{first} {last}'. Abortando este usuário."
                                )
                                break
                            continue
                    else:
                        created_username, error = self._try_create_user(username, password, valid_until)
                except Exception as e:
                    created_username, error = None, e
                if created_username:
                    if group_name:
                        self.add_user_to_group(created_username, group_name)
                    created.append(created_username)
                    break
                else:
                    # Decide se é duplicidade: tentar outro username; senão abortar este usuário
                    if self._is_duplicate_error(error):
                        tentativa += 1
                        if tentativa > 100:
                            self.logger.error(
                                f"[{self.operador}] Muitas tentativas para gerar username baseado em '{first} {last}'. Abortando este usuário."
                            )
                            break
                        continue
                    else:
                        self.logger.error(
                            f"[{self.operador}] Falha ao criar usuário '{username}': {error}"
                        )
                        break
        return created

    # ----------------- Helpers internos -----------------
    def _is_duplicate_error(self, error: Exception | None) -> bool:
        if not error:
            return False
        msg_low = str(error).lower()
        try:
            norm = unicodedata.normalize("NFKD", msg_low).encode("ascii", "ignore").decode("ascii")
        except Exception:
            norm = msg_low
        return (
            "ja existe" in norm
            or "already exists" in norm
            or ("existe" in msg_low and "nao existe" not in msg_low)
        )

    def _try_create_user(self, username: str, password: str, valid_until: str | None):
        try:
            created = self.create_user(username, password, valid_until)
            return created, None
        except Exception as e:
            return None, e

    def get_user(self, username: str) -> Optional[User]:
        try:
            return self.dao.find_user_by_name(username)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao obter usuário '{username}': {e}")
            return None

    def list_users(self) -> List[str]:
        try:
            return self.dao.list_users()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar usuários: {e}")
            return []

    def update_user(self, username: str, **updates) -> bool:
        try:
            if not self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' não existe.")
            with self.dao.transaction():
                self.dao.update_user(username, **updates)
            self.logger.info(f"[{self.operador}] Atualizou usuário: {username} {updates}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao atualizar usuário '{username}': {e}")
            return False

    def renew_user_validity(self, username: str, new_date: str) -> bool:
        """Renova a validade de um usuário existente."""
        return self.update_user(username, valid_until=new_date)

    def delete_user(self, username: str) -> bool:
        dados_antes = None
        sucesso = False
        
        try:
            # Capturar dados antes da exclusão
            user = self.dao.find_user_by_name(username)
            if user:
                dados_antes = {
                    'username': user.username,
                    'oid': user.oid,
                    'can_login': user.can_login,
                    'valid_until': user.valid_until.isoformat() if user.valid_until else None
                }
            
            # Limpeza de objetos antes do DROP ROLE (opcional mas boa prática)
            with self.dao.transaction():
                with self.dao.conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                            sql.Identifier(username)
                        )
                    )

                self.dao.delete_user(username)

                sucesso = True
                if self.audit_manager:
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='DELETE_USER',
                        objeto_tipo='USER',
                        objeto_nome=username,
                        dados_antes=dados_antes,
                        sucesso=sucesso
                    )

            self.logger.info(f"[{self.operador}] Excluiu usuário: {username}")

            return True
            
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao excluir usuário '{username}': {e}")
            
            # Registrar falha na auditoria
            if self.audit_manager:
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='DELETE_USER',
                        objeto_tipo='USER',
                        objeto_nome=username,
                        detalhes={'error': str(e)},
                        dados_antes=dados_antes,
                        sucesso=False
                    )
            
            return False

    def change_password(self, username: str, new_password: str) -> bool:
        try:
            if not self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' não existe.")
            with self.dao.transaction():
                with self.dao.conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(
                            sql.Identifier(username)
                        ),
                        (new_password,),
                    )
            self.logger.info(f"[{self.operador}] Alterou senha do usuário: {username}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao alterar senha de '{username}': {e}")
            return False

    # Métodos de grupo
    def create_group(self, group_name: str) -> str:
        try:
            config = load_config()
            prefix = config.get("group_prefix", "grp_")
            if not group_name.startswith(prefix):
                raise ValueError(f"Nome de grupo deve começar com '{prefix}'.")
            if group_name in self.dao.list_groups():
                raise ValueError(f"Grupo '{group_name}' já existe.")
            with self.dao.transaction():
                self.dao.create_group(group_name)
            self.logger.info(f"[{self.operador}] Criou grupo: {group_name}")
            return group_name
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao criar grupo '{group_name}': {e}")
            raise

    def delete_group(self, group_name: str) -> bool: # <-- NOVO MÉTODO ADICIONADO
        try:
            with self.dao.transaction():
                self.dao.delete_group(group_name)
            self.logger.info(f"[{self.operador}] Excluiu grupo: {group_name}")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao excluir grupo '{group_name}': {e}")
            return False

    def delete_group_and_members(self, group_name: str) -> bool:
        try:
            members = self.dao.list_group_members(group_name)
            for user in members:
                if not self.delete_user(user):
                    raise RuntimeError(f"Falha ao excluir usuário {user}")
            with self.dao.transaction():
                self.dao.delete_group(group_name)
            self.logger.info(
                f"[{self.operador}] Excluiu grupo '{group_name}' e seus membros: {members}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao excluir grupo '{group_name}' e seus membros: {e}"
            )
            return False

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        try:
            with self.dao.transaction():
                self.dao.add_user_to_group(username, group_name)
            self.logger.info(f"[{self.operador}] Adicionou usuário '{username}' ao grupo '{group_name}'")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao adicionar '{username}' ao grupo '{group_name}': {e}")
            return False

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        try:
            with self.dao.transaction():
                self.dao.remove_user_from_group(username, group_name)
            self.logger.info(f"[{self.operador}] Removeu usuário '{username}' do grupo '{group_name}'")
            return True
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao remover '{username}' do grupo '{group_name}': {e}")
            return False

    def transfer_user_group(self, username: str, old_group: str, new_group: str) -> bool:
        detalhes = {"from_group": old_group, "to_group": new_group}
        try:
            with self.dao.transaction():
                self.dao.remove_user_from_group(username, old_group)
                self.dao.add_user_to_group(username, new_group)
                if self.audit_manager:
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao="TRANSFER_USER_GROUP",
                        objeto_tipo="USER",
                        objeto_nome=username,
                        detalhes=detalhes,
                        sucesso=True,
                    )
            self.logger.info(
                f"[{self.operador}] Transferiu usuário '{username}' do grupo '{old_group}' para '{new_group}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao transferir '{username}' de '{old_group}' para '{new_group}': {e}"
            )
            if self.audit_manager:
                detalhes["error"] = str(e)
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao="TRANSFER_USER_GROUP",
                        objeto_tipo="USER",
                        objeto_nome=username,
                        detalhes=detalhes,
                        sucesso=False,
                    )
            return False

    def list_group_members(self, group_name: str) -> List[str]:
        try:
            return self.dao.list_group_members(group_name)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar membros do grupo '{group_name}': {e}")
            return []

    def list_user_groups(self, username: str) -> List[str]:
        try:
            return self.dao.list_user_groups(username)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos do usuário '{username}': {e}")
            return []

    def list_groups(self) -> List[str]:
        try:
            return self.dao.list_groups()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos: {e}")
            return []

    # Métodos de tabelas e privilégios ------------------------------------

    def list_tables_by_schema(self, **kwargs) -> Dict[str, List[str]]:
        try:
            return self.dao.list_tables_by_schema(**kwargs)
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar tabelas: {e}")
            return {}

    def get_group_privileges(self, group_name: str) -> Dict[str, Dict[str, Set[str]]]:
        try:
            return self.dao.get_group_privileges(group_name)
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Erro ao obter privilégios do grupo '{group_name}': {e}"
            )
            return {}

    def set_group_privileges(self, group_name: str, privileges: Dict[str, Dict[str, Set[str]]]) -> bool:
        try:
            with self.dao.transaction():
                self.dao.apply_group_privileges(group_name, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios do grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios do grupo '{group_name}': {e}"
            )
            return False

    def grant_database_privileges(self, group_name: str, privileges: Set[str]) -> bool:
        try:
            with self.dao.transaction():
                self.dao.grant_database_privileges(group_name, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios de banco do grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios de banco do grupo '{group_name}': {e}"
            )
            return False

    def grant_schema_privileges(self, group_name: str, schema: str, privileges: Set[str]) -> bool:
        try:
            with self.dao.transaction():
                self.dao.grant_schema_privileges(group_name, schema, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios do schema '{schema}' para o grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios do schema '{schema}' para o grupo '{group_name}': {e}"
            )
            return False

    def alter_default_privileges(
        self, group_name: str, schema: str, obj_type: str, privileges: Set[str]
    ) -> bool:
        """Configura ``ALTER DEFAULT PRIVILEGES`` para novos objetos."""
        try:
            with self.dao.transaction():
                self.dao.alter_default_privileges(group_name, schema, obj_type, privileges)
            self.logger.info(
                f"[{self.operador}] Atualizou default privileges de '{obj_type}' no schema '{schema}' para o grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar default privileges de '{obj_type}' no schema '{schema}' para o grupo '{group_name}': {e}"
            )
            return False

    def apply_template_to_group(self, group_name: str, template: str) -> bool:
        """Aplica um template hierárquico de permissões (banco/schema/tabelas)."""
        try:
            from config.permission_templates import PERMISSION_TEMPLATES

            tpl = PERMISSION_TEMPLATES.get(template)
            if tpl is None:
                raise ValueError(f"Template '{template}' não encontrado.")

            db_perms = tpl.get("database", {})
            schema_perms = tpl.get("schemas", {})
            table_perms = tpl.get("tables", {})
            future_perms = tpl.get("future", {})

            with self.dao.transaction():
                dbname = self.dao.conn.get_dsn_parameters().get("dbname")
                if "*" in db_perms:
                    self.dao.grant_database_privileges(group_name, set(db_perms["*"]))
                elif dbname in db_perms:
                    self.dao.grant_database_privileges(group_name, set(db_perms[dbname]))

                for schema, perms in schema_perms.items():
                    self.dao.grant_schema_privileges(group_name, schema, set(perms))

                if table_perms:
                    tables = self.list_tables_by_schema()
                    privileges: Dict[str, Dict[str, Set[str]]] = {}
                    for schema, tbls in tables.items():
                        if schema in table_perms:
                            schema_def = table_perms[schema]
                            if isinstance(schema_def, dict):
                                for tbl, perms in schema_def.items():
                                    privileges.setdefault(schema, {})[tbl] = set(perms)
                            else:
                                perms_set = set(schema_def)
                                for tbl in tbls:
                                    privileges.setdefault(schema, {})[tbl] = perms_set
                        elif "*" in table_perms:
                            perms_set = set(table_perms["*"])
                            for tbl in tbls:
                                privileges.setdefault(schema, {})[tbl] = perms_set
                    if privileges:
                        self.dao.apply_group_privileges(group_name, privileges)

                for schema, obj_perms in future_perms.items():
                    for obj_type, perms in obj_perms.items():
                        self.dao.alter_default_privileges(
                            group_name, schema, obj_type, set(perms)
                        )

            self.logger.info(
                f"[{self.operador}] Aplicou template '{template}' ao grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao aplicar template '{template}' ao grupo '{group_name}': {e}"
            )
            return False
