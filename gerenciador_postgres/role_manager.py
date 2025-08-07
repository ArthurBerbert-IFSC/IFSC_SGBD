from .db_manager import DBManager
from .data_models import User, Group
from typing import Optional, List
import logging
from psycopg2 import sql

class RoleManager:
    """Camada de serviço: orquestra operações, valida regras e controla transações."""
    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema'):
        self.dao = dao
        self.logger = logger
        self.operador = operador

    def create_user(self, username: str, password: str) -> str:
        try:
            if self.dao.find_user_by_name(username):
                raise ValueError(f"Usuário '{username}' já existe.")
            self.dao.insert_user(username, password)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Criou usuário: {username}")
            return username
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao criar usuário '{username}': {e}")
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
        try:
            # Limpeza de objetos antes do DROP ROLE (opcional mas boa prática)
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                        sql.Identifier(username)
                    )
                )
            self.dao.delete_user(username)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Excluiu usuário: {username}")
            return True
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao excluir usuário '{username}': {e}")
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

    def list_groups(self) -> List[str]:
        try:
            return self.dao.list_groups()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar grupos: {e}")
            return []