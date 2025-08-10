import logging
from .db_manager import DBManager
from .config_manager import load_config


class SchemaManager:
    """Camada de serviço: orquestra operações e controla transações de schemas."""

    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema', audit_manager=None):
        self.dao = dao
        self.logger = logger
        self.operador = operador
        self.audit_manager = audit_manager
        self.allowed_group = load_config().get('schema_creation_group', 'Professores')

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
        dados_depois = None
        sucesso = False
        
        if not (self._is_superuser(user) or self._has_role(user, self.allowed_group)):
            self.logger.error(
                f"[{self.operador}] Usuário '{user}' não tem permissão para criar schema"
            )
            raise PermissionError(
                f"Apenas {self.allowed_group} ou superusuários podem criar schemas."
            )
        
        try:
            with self.dao.transaction():
                with self.dao.conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_has_role(%s, %s, 'member')",
                        (self.operador, self.allowed_group),
                    )
                    has_permission = cur.fetchone()[0]
                if not has_permission:
                    self.logger.error(
                        f"[{self.operador}] Permissão negada para criar schema '{name}'"
                    )
                    raise PermissionError(
                        f"Usuário não pertence ao grupo '{self.allowed_group}'"
                    )

                self.dao.create_schema(name, owner)
                if hasattr(self.dao, 'enable_postgis'):
                    try:
                        self.dao.enable_postgis(name)
                    except Exception as e:
                        self.logger.warning(
                            f"[{self.operador}] Falha ao habilitar PostGIS no schema '{name}': {e}"
                        )

                dados_depois = {'schema_name': name, 'owner': owner}
                sucesso = True

                if self.audit_manager:
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='CREATE_SCHEMA',
                        objeto_tipo='SCHEMA',
                        objeto_nome=name,
                        detalhes={'owner': owner, 'postgis_enabled': True},
                        dados_depois=dados_depois,
                        sucesso=sucesso
                    )

            self.logger.info(f"[{self.operador}] Criou schema: {name}")
                
        except PermissionError:
            # Registrar falha de permissão na auditoria
            if self.audit_manager:
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='CREATE_SCHEMA',
                        objeto_tipo='SCHEMA',
                        objeto_nome=name,
                        detalhes={'error': 'Permission denied', 'owner': owner},
                        sucesso=False
                    )
            raise
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao criar schema '{name}': {e}")

            # Registrar falha na auditoria
            if self.audit_manager:
                with self.dao.transaction():
                    self.audit_manager.log_operation(
                        operador=self.operador,
                        operacao='CREATE_SCHEMA',
                        objeto_tipo='SCHEMA',
                        objeto_nome=name,
                        detalhes={'error': str(e), 'owner': owner},
                        sucesso=False
                    )

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
            with self.dao.transaction():
                self.dao.drop_schema(name, cascade)
            self.logger.info(f"[{self.operador}] Removeu schema: {name}")
        except Exception as e:
            self.logger.error(f"[{self.operador}] Falha ao remover schema '{name}': {e}")
            raise

    def change_owner(self, name: str, new_owner: str):
        try:
            with self.dao.transaction():
                self.dao.alter_schema_owner(name, new_owner)
            self.logger.info(
                f"[{self.operador}] Alterou proprietário do schema '{name}' para '{new_owner}'"
            )
        except Exception as e:
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

