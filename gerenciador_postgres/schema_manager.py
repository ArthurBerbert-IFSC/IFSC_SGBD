import logging
from .db_manager import DBManager


class SchemaManager:
    """Camada de serviço: orquestra operações e controla transações de schemas."""

    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema'):
        self.dao = dao
        self.logger = logger
        self.operador = operador

    def create_schema(self, name: str, owner: str | None = None):
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_has_role(%s, %s, 'member')",
                    (self.operador, 'Professores'),
                )
                has_permission = cur.fetchone()[0]
            if not has_permission:
                self.dao.conn.rollback()
                self.logger.error(
                    f"[{self.operador}] Permissão negada para criar schema '{name}'"
                )
                raise PermissionError(
                    "Usuário não pertence ao grupo 'Professores'"
                )

            self.dao.create_schema(name, owner)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Criou schema: {name}")
        except PermissionError:
            raise
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao criar schema '{name}': {e}")
            raise

    def delete_schema(self, name: str, cascade: bool = False):
        try:
            self.dao.drop_schema(name, cascade)
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Removeu schema: {name}")
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao remover schema '{name}': {e}")
            raise

    def change_owner(self, name: str, new_owner: str):
        try:
            self.dao.alter_schema_owner(name, new_owner)
            self.dao.conn.commit()
            self.logger.info(
                f"[{self.operador}] Alterou proprietário do schema '{name}' para '{new_owner}'"
            )
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(
                f"[{self.operador}] Falha ao alterar proprietário do schema '{name}': {e}"
            )
            raise

    def list_schemas(self) -> list[str]:
        try:
            return self.dao.list_schemas()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar schemas: {e}")
            return []

