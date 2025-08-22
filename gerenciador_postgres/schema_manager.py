import logging
from .db_manager import DBManager
from .config_manager import load_config

# Core infrastructure imports
from .core import (
    get_metrics, get_cache, get_logger, get_event_bus,
    audit_operation, OperationResult, get_task_manager
)


class SchemaManager:
    """Camada de serviço: orquestra operações e controla transações de schemas."""

    def __init__(self, dao: DBManager, logger: logging.Logger, operador: str = 'sistema', audit_manager=None):
        self.dao = dao
        self.logger = logger or get_logger(__name__)
        self.operador = operador
        self.audit_manager = audit_manager
        self.allowed_group = load_config().get('schema_creation_group', 'Professores')
        
        # Core services
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.event_bus = get_event_bus()
        self.task_manager = get_task_manager()

    # --- Helpers de permissão -------------------------------------------------
    def _current_user(self) -> str:
        with self.dao.conn.cursor() as cur:
            cur.execute('SELECT current_user')
            return cur.fetchone()[0]

    def _has_role(self, username: str, role: str) -> bool:
        """Verifica se usuário tem papel específico (com cache)."""
        cache_key = f"user_role:{username}:{role}"
        result = self.cache.get(cache_key)
        
        if result is None:
            with self.dao.conn.cursor() as cur:
                cur.execute("SELECT pg_has_role(%s, %s, 'member')", (username, role))
                row = cur.fetchone()
                result = bool(row and row[0])
            
            # Cache for 5 minutes
            self.cache.set(cache_key, result, ttl=300, tags=["user_roles"])
            
        return result

    def _is_superuser(self, username: str) -> bool:
        """Verifica se usuário é superuser (com cache)."""
        cache_key = f"is_superuser:{username}"
        result = self.cache.get(cache_key)
        
        if result is None:
            with self.dao.conn.cursor() as cur:
                cur.execute("SELECT usesuper FROM pg_user WHERE usename = %s", (username,))
                row = cur.fetchone()
                result = bool(row and row[0])
            
            # Cache for 10 minutes (superuser status rarely changes)
            self.cache.set(cache_key, result, ttl=600, tags=["user_roles"])
            
        return result

    def _role_exists(self, role: str) -> bool:
        """Verifica se papel existe (com cache)."""
        if not role:
            return False
            
        cache_key = f"role_exists:{role}"
        result = self.cache.get(cache_key)
        
        if result is None:
            with self.dao.conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                result = cur.fetchone() is not None
            
            # Cache for 5 minutes
            self.cache.set(cache_key, result, ttl=300, tags=["roles"])
            
        return result

    def _get_schema_owner(self, schema: str) -> str | None:
        """Obtém proprietário do schema (com cache)."""
        cache_key = f"schema_owner:{schema}"
        result = self.cache.get(cache_key)
        
        if result is None:
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
                result = row[0] if row else None
            
            # Cache for 10 minutes
            self.cache.set(cache_key, result, ttl=600, tags=["schemas"])
            
        return result

    # --- Operações ------------------------------------------------------------
    def create_schema(self, name: str, owner: str | None = None):
        user = self._current_user()
        dados_depois = None
        sucesso = False
        
        # Verifica existência do grupo configurado; se não existir, cai para regra só superusuário
        group_exists = self._role_exists(self.allowed_group)
        has_group_perm = False
        if group_exists:
            has_group_perm = self._has_role(user, self.allowed_group)
        else:
            if self.allowed_group:
                self.logger.warning(
                    f"Grupo configurado 'schema_creation_group'='{self.allowed_group}' não existe. Apenas superusuários poderão criar schemas até corrigir config ou recriar o role."
                )
        if not (self._is_superuser(user) or (group_exists and has_group_perm)):
            self.logger.error(
                f"[{self.operador}] Usuário '{user}' não tem permissão para criar schema"
            )
            if group_exists:
                raise PermissionError(
                    f"Apenas {self.allowed_group} ou superusuários podem criar schemas."
                )
            else:
                raise PermissionError(
                    "Grupo configurado para criação de schemas não existe; somente superusuários podem criar."
                )
        
        try:
            with self.dao.transaction():
                if group_exists:
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

                # (Auto-config de privilégios removida para permitir escolha manual pelo usuário.)

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

    # --- Auxiliar para GUI --------------------------------------------------
    def list_owner_candidates(self, include_superusers: bool = True) -> list[str]:
        """Retorna lista de roles candidatos a serem owners de schemas.

        Inclui todos os roles não internos. Opcionalmente filtra superusuários
        se ``include_superusers`` for ``False``.
        """
        try:
            roles = self.dao.list_all_roles()
            if not include_superusers:
                # Filtra superusuários consultando catalogo
                with self.dao.conn.cursor() as cur:
                    cur.execute("SELECT rolname FROM pg_roles WHERE rolsuper")
                    supers = {r[0] for r in cur.fetchall()}
                roles = [r for r in roles if r not in supers]
            return roles
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar candidatos a owner: {e}")
            return []

    def list_superusers(self) -> list[str]:
        """Retorna lista de roles que são superusuários."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute("SELECT rolname FROM pg_roles WHERE rolsuper ORDER BY rolname")
                return [r[0] for r in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"[{self.operador}] Erro ao listar superusuários: {e}")
            return []

