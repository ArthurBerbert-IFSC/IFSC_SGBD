import logging
from .db_manager import DBManager


class SchemaManager:
    """Camada de serviço: orquestra operações e controla transações de schemas."""

    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema'):
        self.dao = dao
        self.logger = logger
        self.operador = operador

    # --- Helpers de permissão -------------------------------------------------
    def _current_user(self) -> str:
        with self.dao.conn.cursor() as cur:
            cur.execute('SELECT current_user')
            return cur.fetchone()[0]

    def _has_role(self, username: str, role: str) -> bool:
        with self.dao.conn.cursor() as cur:
            cur.execute("SELECT pg_has_role(%s, %s, 'member')", (username, role))
            row = cur.fetchone()
            return bool(row and row[0])

    def _is_superuser(self, username: str) -> bool:
        with self.dao.conn.cursor() as cur:
            cur.execute("SELECT usesuper FROM pg_user WHERE usename = %s", (username,))
            row = cur.fetchone()
            return bool(row and row[0])

    def _get_schema_owner(self, schema: str) -> str | None:
        with self.dao.conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_catalog.pg_get_userbyid(nspowner)
                FROM pg_namespace
                WHERE nspname = %s
                """,
                (schema,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    # --- Operações ------------------------------------------------------------
    def create_schema(self, name: str, owner: str | None = None):
        user = self._current_user()
        if not (self._is_superuser(user) or self._has_role(user, 'Professores')):
            self.logger.error(
                f"[{self.operador}] Usuário '{user}' não tem permissão para criar schema"
            )
            raise PermissionError('Apenas Professores ou superusuários podem criar schemas.')
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
            if hasattr(self.dao, 'enable_postgis'):
                try:
                    self.dao.enable_postgis(name)
                except Exception as e:
                    self.logger.warning(
                        f"[{self.operador}] Falha ao habilitar PostGIS no schema '{name}': {e}"
                    )
            self.dao.conn.commit()
            self.logger.info(f"[{self.operador}] Criou schema: {name}")
        except PermissionError:
            raise
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"[{self.operador}] Falha ao criar schema '{name}': {e}")
            raise

    def delete_schema(self, name: str, cascade: bool = False):
        user = self._current_user()
        owner = self._get_schema_owner(name)
        if not (self._is_superuser(user) or user == owner):
            self.logger.error(
                f"[{self.operador}] Usuário '{user}' não pode remover schema '{name}'"
            )
            raise PermissionError('Apenas o proprietário ou um superusuário pode remover schemas.')
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

    def list_roles(self) -> list[str]:
        try:
            return self.dao.list_roles()
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar roles: {e}")
            return []

