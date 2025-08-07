from .db_manager import DBManager
from .data_models import User, Group
from typing import Optional, List, Dict, Set
import logging
from psycopg2 import sql

class RoleManager:
    """Camada de serviço: orquestra operações, valida regras e controla transações."""
    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema', audit_manager=None):
        self.dao = dao
        self.logger = logger
        self.operador = operador
        self.audit_manager = audit_manager

    def create_user(self, username: str, password: str) -> str:
        dados_antes = None
        dados_depois = None
        sucesso = False
        
        try:
            if self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' já existe.")
            
            self.dao.insert_user(username, password)
            self.dao.conn.commit()
            
            dados_depois = {'username': username, 'can_login': True}
            sucesso = True
            
            self.logger.info(f"[{self.operador}] Criou usuário: {username}")
            
            # Registrar auditoria
            if self.audit_manager:
                self.audit_manager.log_operation(
                    operador=self.operador,
                    operacao='CREATE_USER',
                    objeto_tipo='USER',
                    objeto_nome=username,
                    detalhes={'password_set': True},
                    dados_antes=dados_antes,
                    dados_depois=dados_depois,
                    sucesso=sucesso
                )
            
            return username
            
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao criar usuário '{username}': {e}")
            
            # Registrar falha na auditoria
            if self.audit_manager:
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
            self.dao.update_user(username, **updates)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Atualizou usuário: {username} {updates}")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao atualizar usuário '{username}': {e}")
            return False

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
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                        sql.Identifier(username)
                    )
                )
            
            self.dao.delete_user(username)
            self.dao.conn.commit()
            sucesso = True
            
            self.logger.info(f"[{self.operador}] Excluiu usuário: {username}")
            
            # Registrar auditoria
            if self.audit_manager:
                self.audit_manager.log_operation(
                    operador=self.operador,
                    operacao='DELETE_USER',
                    objeto_tipo='USER',
                    objeto_nome=username,
                    dados_antes=dados_antes,
                    sucesso=sucesso
                )
            
            return True
            
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao excluir usuário '{username}': {e}")
            
            # Registrar falha na auditoria
            if self.audit_manager:
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
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(
                        sql.Identifier(username)
                    ),
                    (new_password,),
                )
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Alterou senha do usuário: {username}")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao alterar senha de '{username}': {e}")
            return False

    def bulk_create_users(self, users: Dict[str, str]) -> List[str]:
        criados: List[str] = []
        try:
            for username, password in users.items():
                if self.dao.find_user_by_name(username):
                    raise ValueError(f"Usuário '{username}' já existe.")
                self.dao.insert_user(username, password)
                criados.append(username)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Criou usuários em lote: {', '.join(criados)}"
            )
            return criados
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao criar usuários em lote: {e}"
            )
            return []

    # Métodos de grupo
    def create_group(self, group_name: str) -> str:
        try:
            if not group_name.startswith('grp_'):
                raise ValueError("Nome de grupo deve começar com 'grp_'.")
            if group_name in self.dao.list_groups():
                raise ValueError(f"Grupo '{group_name}' já existe.")
            self.dao.create_group(group_name)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Criou grupo: {group_name}")
            return group_name
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao criar grupo '{group_name}': {e}")
            raise

    def delete_group(self, group_name: str) -> bool: # <-- NOVO MÉTODO ADICIONADO
        try:
            self.dao.delete_group(group_name)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Excluiu grupo: {group_name}")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao excluir grupo '{group_name}': {e}")
            return False

    def delete_group_and_members(self, group_name: str) -> bool:
        try:
            members = self.dao.list_group_members(group_name)
            for user in members:
                if not self.delete_user(user):
                    raise RuntimeError(f"Falha ao excluir usuário {user}")
            self.dao.delete_group(group_name)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Excluiu grupo '{group_name}' e seus membros: {members}"
            )
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao excluir grupo '{group_name}' e seus membros: {e}"
            )
            return False

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        try:
            self.dao.add_user_to_group(username, group_name)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Adicionou usuário '{username}' ao grupo '{group_name}'")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao adicionar '{username}' ao grupo '{group_name}': {e}")
            return False

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        try:
            self.dao.remove_user_from_group(username, group_name)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Removeu usuário '{username}' do grupo '{group_name}'")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao remover '{username}' do grupo '{group_name}': {e}")
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
            self.logger.error(
                f"[{self.operador}] Erro ao listar grupos do usuário '{username}': {e}"
            )
            return []

    def list_groups(self) -> List[str]:
        try:
            return self.dao.list_groups()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos: {e}")
            return []

    # Métodos de tabelas e privilégios ------------------------------------

    def list_tables_by_schema(self) -> Dict[str, List[str]]:
        try:
            return self.dao.list_tables_by_schema()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar tabelas: {e}")
            return {}

    def list_schemas_with_tables(self) -> Dict[str, List[str]]:
        try:
            return self.dao.list_schemas_with_tables()
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Erro ao listar schemas e tabelas: {e}"
            )
            return {}

    def set_group_privileges(self, group_name: str, privileges: Dict[str, Dict[str, Set[str]]]) -> bool:
        try:
            self.dao.apply_group_privileges(group_name, privileges)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Atualizou privilégios do grupo '{group_name}'"
            )
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao atualizar privilégios do grupo '{group_name}': {e}"
            )
            return False

    def apply_template_to_group(self, group_name: str, template: str) -> bool:
        """Aplica um template de permissões a todas as tabelas para o grupo."""
        try:
            from config.permission_templates import PERMISSION_TEMPLATES

            perms = PERMISSION_TEMPLATES.get(template)
            if perms is None:
                raise ValueError(f"Template '{template}' não encontrado.")

            tables = self.list_tables_by_schema()
            privileges: Dict[str, Dict[str, Set[str]]] = {}
            for schema, tbls in tables.items():
                for table in tbls:
                    privileges.setdefault(schema, {})[table] = set(perms)

            return self.set_group_privileges(group_name, privileges)
        except Exception as e:
            self.logger.error(
                f"[{self.operador}] Falha ao aplicar template '{template}' ao grupo '{group_name}': {e}"
            )
            return False

    def grant_privileges(
        self, role: str, schema: str, table: str, privileges: Set[str]
    ) -> bool:
        try:
            self.dao.grant_privileges(role, schema, table, privileges)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Concedeu {privileges} em {schema}.{table} a {role}"
            )
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao conceder privilégios {privileges} em {schema}.{table} a {role}: {e}"
            )
            return False

    def revoke_privileges(
        self, role: str, schema: str, table: str, privileges: Set[str] | None = None
    ) -> bool:
        try:
            self.dao.revoke_privileges(role, schema, table, privileges)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Revogou {privileges or 'ALL'} em {schema}.{table} de {role}"
            )
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao revogar privilégios em {schema}.{table} de {role}: {e}"
            )
            return False
