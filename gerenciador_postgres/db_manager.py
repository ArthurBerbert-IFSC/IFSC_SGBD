import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection
from contextlib import contextmanager
from .data_models import User, Group
from typing import Optional, List, Dict, Set, Callable
import logging

from contracts.permission_contract import filter_managed

logger = logging.getLogger(__name__)
logger.propagate = True


PRIVILEGE_WHITELIST = {
    "DATABASE": {"CREATE", "CONNECT", "TEMPORARY"},
    "SCHEMA": {"CREATE", "USAGE"},
    "TABLE": {"SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"},
    "SEQUENCE": {"USAGE", "SELECT", "UPDATE"},
    "FUNCTION": {"EXECUTE"},
    "TYPE": {"USAGE"},
}

# Map codes from pg ACLs to human readable privilege names
PG_PRIVCODE_TO_NAME = {
    "a": "INSERT",
    "r": "SELECT",
    "w": "UPDATE",
    "d": "DELETE",
    "D": "TRUNCATE",
    "x": "REFERENCES",
    "t": "TRIGGER",
}

# Supported object type identifiers for default privileges
OBJECT_TYPES = {"tables", "sequences", "functions", "types"}

# Mapping between friendly names and SQL keywords used by ALTER DEFAULT PRIVILEGES
OBJECT_TYPE_MAPS = {
    "tables": "TABLES",
    "sequences": "SEQUENCES",
    "functions": "FUNCTIONS",
    "types": "TYPES",
}

# Mapping to pg_default_acl objtype codes used by get_default_privileges
OBJECT_TYPE_CODES = {
    "tables": "r",
    "sequences": "S",
    "functions": "f",
    "types": "T",
}


class DBManager:
    """Camada de acesso a dados para gerenciamento de roles e schemas."""

    def __init__(self, conn: connection | Callable[[], connection]):
        """Inicializa o ``DBManager``.

        O parâmetro ``conn`` pode ser um objeto de conexão já aberto ou uma
        função/callable que retorne uma conexão. Este último formato permite
        que cada *thread* obtenha sua própria conexão sob demanda.
        """

        if callable(conn):
            self._conn_provider = conn
        else:
            if not conn or not hasattr(conn, "cursor"):
                raise ValueError("Conexão inválida para DBManager")
            self._conn_provider = lambda conn=conn: conn

    # ------------------------------------------------------------------
    @property
    def conn(self) -> connection:
        return self._conn_provider()

    # ------------------------------------------------------------------
    def _reset_if_aborted(self):
        """Efetua rollback silencioso se a conexão estiver em estado de erro.

        Situações como "current transaction is aborted" deixam a conexão
        inutilizável até um ``ROLLBACK``. Este helper é chamado no início
        de operações de leitura para recuperar automaticamente após falhas
        anteriores.
        """
        try:
            from psycopg2 import extensions as _ext
            status = self.conn.get_transaction_status()
            if status == _ext.TRANSACTION_STATUS_INERROR:
                logger.warning("Transação anterior abortada detectada; executando rollback automático.")
                self.conn.rollback()
        except Exception:
            pass

    @contextmanager
    def transaction(self):
        """Contexto para controle de transações.

        Efetua ``commit`` ao término bem-sucedido do bloco e ``rollback``
        automaticamente em caso de exceções.
        """
        conn = self.conn
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    def server_version_num(self) -> int:
        """Return PostgreSQL server version as integer (e.g. 150002)."""
        with self.conn.cursor() as cur:
            cur.execute("SHOW server_version_num")
            row = cur.fetchone()
            try:
                return int(row[0])
            except (TypeError, ValueError, IndexError):
                return 0

    def find_user_by_name(self, username: str) -> Optional[User]:
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname, oid, rolvaliduntil, rolcanlogin
                FROM pg_roles
                WHERE rolname = %s
            """, (username,))
            row = cur.fetchone()
            if row:
                return User(username=row[0], oid=row[1], valid_until=row[2], can_login=row[3])
            return None

    def insert_user(self, username: str, password_hash: str, valid_until: str | None = None):
        with self.conn.cursor() as cur:
            if valid_until:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD %s VALID UNTIL %s"
                    ).format(sql.Identifier(username)),
                    (password_hash, valid_until),
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(username)
                    ),
                    (password_hash,),
                )

    def update_user(self, username: str, **fields):
        with self.conn.cursor() as cur:
            clauses = []
            params = []
            if 'valid_until' in fields:
                clauses.append(sql.SQL("VALID UNTIL %s"))
                params.append(fields['valid_until'])
            if 'can_login' in fields:
                clauses.append(
                    sql.SQL("LOGIN") if fields['can_login'] else sql.SQL("NOLOGIN")
                )
            if not clauses:
                return
            query = (
                sql.SQL("ALTER ROLE {} ").format(sql.Identifier(username))
                + sql.SQL(" ").join(clauses)
            )
            cur.execute(query, params)

    def delete_user(self, username: str):
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(username)))

    def list_users(self) -> List[str]:
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = true
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            # Anteriormente filtrava por padrões do permission_contract (filter_managed),
            # o que ocultava usuários gerados no formato primeiro.ultimo.
            # Agora retornamos todos os roles de login não-sistema.
            return [row[0] for row in cur.fetchall()]

    # --- Contagens rápidas para dashboard ---
    def count_users(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM pg_roles
                WHERE rolcanlogin = true
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                """
            )
            return cur.fetchone()[0]

    def count_groups(self, prefix: str = 'grp_') -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM pg_roles
                WHERE rolcanlogin = false
                  AND rolname LIKE %s
                """,
                (f"{prefix}%",),
            )
            return cur.fetchone()[0]

    def count_schemas(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM information_schema.schemata
                WHERE schema_name NOT LIKE 'pg_%'
                  AND schema_name <> 'information_schema'
                """
            )
            return cur.fetchone()[0]

    def count_tables(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r'
                  AND n.nspname NOT LIKE 'pg_%'
                  AND n.nspname <> 'information_schema'
                """
            )
            return cur.fetchone()[0]

    def create_group(self, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(group_name))
            )

    def delete_group(self, group_name: str):  # <-- NOVO MÉTODO ADICIONADO
        with self.conn.cursor() as cur:
            # 1) Reassign ownership de objetos (defensivo; grupos geralmente não possuem objetos)
            try:
                cur.execute(
                    sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                        sql.Identifier(group_name)
                    )
                )
            except psycopg2.Error as e:
                # Prossegue mesmo que o grupo não possua objetos próprios
                logger.debug(
                    "Sem objetos para reatribuir do grupo %s: %s", group_name, e
                )

            # 2) Remover privilégios concedidos ao grupo no banco atual
            try:
                cur.execute(
                    sql.SQL("DROP OWNED BY {}" ).format(sql.Identifier(group_name))
                )
            except psycopg2.Error as e:
                # Alguns bancos/versões podem restringir; seguimos com o melhor esforço
                logger.debug(
                    "Não foi possível remover privilégios do grupo %s: %s",
                    group_name,
                    e,
                )

            # 3) Revogar o grupo de quaisquer membros restantes (defensivo)
            cur.execute(
                """
                SELECT u.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE g.rolname = %s
                """,
                (group_name,),
            )
            for (member_name,) in cur.fetchall():
                try:
                    cur.execute(
                        sql.SQL("REVOKE {} FROM {}" ).format(
                            sql.Identifier(group_name), sql.Identifier(member_name)
                        )
                    )
                except psycopg2.Error as e:
                    logger.warning(
                        "Falha ao revogar membro %s do grupo %s: %s",
                        member_name,
                        group_name,
                        e,
                    )

            # 4) Finalmente, excluir o role do grupo
            cur.execute(sql.SQL("DROP ROLE {}" ).format(sql.Identifier(group_name)))

    def add_user_to_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(group_name),
                    sql.Identifier(username),
                )
            )

    def remove_user_from_group(self, username: str, group_name: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(group_name),
                    sql.Identifier(username),
                )
            )

    def list_group_members(self, group_name: str) -> List[str]:
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT u.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE g.rolname = %s
                ORDER BY u.rolname
            """, (group_name,))
            return [row[0] for row in cur.fetchall()]

    def list_user_groups(self, username: str) -> List[str]:
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT g.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE u.rolname = %s
                ORDER BY g.rolname
            """, (username,))
            # Removido filter_managed para exibir todos os grupos atribuídos
            return [row[0] for row in cur.fetchall()]

    def list_groups(self) -> List[str]:
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = false
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            # Removido filter_managed para permitir visualizar todos os grupos
            return [row[0] for row in cur.fetchall()]

    def list_roles(self) -> List[str]:
        """Retorna todos os roles disponíveis (usuários e grupos)."""
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT rolname FROM pg_roles
                WHERE rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                ORDER BY rolname
                """
            )
            return filter_managed([row[0] for row in cur.fetchall()])

    def list_all_roles(self, include_internal: bool = False) -> List[str]:
        """Lista todos os roles (logins e grupos) opcionando exclusão dos internos.

        Diferente de ``list_roles`` NÃO aplica ``filter_managed`` e portanto
        retorna também usuários sem o prefixo gerenciado, inclusive superusuários.

        Args:
            include_internal: Se ``True`` inclui roles internos (pg_*, rls_*). Normalmente fica False.
        """
        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            if include_internal:
                cur.execute("SELECT rolname FROM pg_roles ORDER BY rolname")
            else:
                cur.execute(
                    """
                    SELECT rolname FROM pg_roles
                    WHERE rolname NOT LIKE 'pg\\_%'
                      AND rolname NOT LIKE 'rls\\_%'
                    ORDER BY rolname
                    """
                )
            return [row[0] for row in cur.fetchall()]

    # Métodos de tabelas e privilégios ------------------------------------

    def list_tables_by_schema(
        self,
        include_types: tuple[str, ...] = ("r", "v"),
        include_schemas: list[str] | None = None,
        exclude_schemas: tuple[str, ...] = ("pg_catalog", "information_schema"),
    ) -> Dict[str, List[str]]:
        """Lista objetos por schema.

        Args:
            include_types: tipos de objetos em ``pg_class`` a serem incluídos
                (``r``=tabelas, ``v``=views, etc.).
            include_schemas: lista de schemas a incluir. Se ``None``, inclui
                todos exceto ``exclude_schemas``.
            exclude_schemas: schemas a ignorar quando ``include_schemas`` for
                ``None``.
        """

        # Determine schemas to include
        if include_schemas is not None:
            schemas = include_schemas
        else:
            schemas = [s for s in self.list_schemas() if s not in exclude_schemas]

        query = [
            "SELECT n.nspname, c.relname",
            "FROM pg_catalog.pg_class c",
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace",
            "WHERE c.relkind = ANY(%s)",
            "AND n.nspname = ANY(%s)",
            "ORDER BY n.nspname, c.relname",
        ]
        sql_query = "\n".join(query)
        params: list[object] = [list(include_types), schemas]

        self._reset_if_aborted()
        with self.conn.cursor() as cur:
            cur.execute(sql_query, params)
            result: Dict[str, List[str]] = {schema: [] for schema in schemas}
            for schema, table in cur.fetchall():
                result.setdefault(schema, []).append(table)
            return result

    def get_group_privileges(self, group: str) -> Dict[str, Dict[str, Set[str]]]:
        """Retorna os privilégios de tabela concedidos a um grupo.

        A consulta utiliza ``pg_catalog`` diretamente com ``aclexplode`` para
        que o resultado preserve informações de ``GRANT OPTION`` (sinalizadas
        por ``"*"`` ao final do nome do privilégio).
        """

        # Importante: "acldefault" espera primeiro argumento do tipo "char",
        # portanto fazemos cast explícito ( 'S'::"char" / 'r'::"char" ) para
        # evitar erro "function acldefault(text, oid) does not exist" em alguns
        # servidores / versões.
        query = (
            """
            SELECT
                n.nspname AS table_schema,
                c.relname AS table_name,
                a.privilege_type,
                a.is_grantable
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(
                COALESCE(
                    c.relacl,
                    acldefault(
                        (CASE WHEN c.relkind = 'S' THEN 'S'::"char" ELSE 'r'::"char" END),
                        c.relowner
                    )
                )
            ) AS a
            JOIN pg_roles gr ON gr.oid = a.grantee
            WHERE gr.rolname = %s
            """
        )
        self._reset_if_aborted()
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (group,))
                result: Dict[str, Dict[str, Set[str]]] = {}
                for schema, table, priv, grantable in cur.fetchall():
                    privname = priv + ("*" if grantable else "")
                    result.setdefault(schema, {}).setdefault(table, set()).add(privname)
                return result
        except Exception as e:
            logger.error("Erro ao obter privilégios de grupo '%s': %s", group, e)
            # Garante que um erro aqui não deixe a transação em estado abortado
            self._reset_if_aborted()
            return {}

    def apply_group_privileges(
        self,
        group: str,
        privileges: Dict[str, Dict[str, Set[str]]],
        obj_type: str = "TABLE",
        check_dependencies: bool = True,
    ):
        """Aplica GRANT/REVOKE para tabelas ou sequências.

        Parameters
        ----------
        group : str
            Role a receber os privilégios.
        privileges : Dict[str, Dict[str, Set[str]]]
            Estrutura ``{schema: {obj: {priv1, priv2}}}``.
        obj_type : str, optional
            ``"TABLE"`` (padrão) ou ``"SEQUENCE"``.
        """

        obj_type = obj_type.upper()
        allowed = PRIVILEGE_WHITELIST.get(obj_type)
        if allowed is None:
            raise ValueError(f"Tipo de objeto '{obj_type}' não suportado")
        keyword = sql.SQL(obj_type)

        # Obtém os privilégios atuais para comparar com os desejados
        current = self.get_group_privileges(group)

        with self.conn.cursor() as cur:
            for schema, objects in privileges.items():
                for name, perms in objects.items():
                    desired = set(perms)
                    invalid = desired - allowed
                    if invalid:
                        raise ValueError(
                            f"Privilégios inválidos para {obj_type}: {', '.join(sorted(invalid))}"
                        )

                    identifier = sql.Identifier(schema, name)
                    existing = current.get(schema, {}).get(name, set())
                    to_grant = desired - existing
                    to_revoke = existing - desired

                    if to_revoke:
                        if check_dependencies:
                            deps = self.get_object_dependencies(schema, name)
                            if deps:
                                raise RuntimeError(
                                    f"[WARN-DEPEND] {schema}.{name} possui dependências: {deps}"
                                )
                        cur.execute(
                            sql.SQL("REVOKE {} ON {} {} FROM {}").format(
                                sql.SQL(", ").join(
                                    sql.SQL(p.rstrip("*")) for p in sorted(to_revoke)
                                ),
                                keyword,
                                identifier,
                                sql.Identifier(group),
                            )
                        )
                    if to_grant:
                        cur.execute(
                            sql.SQL("GRANT {} ON {} {} TO {}").format(
                                sql.SQL(", ").join(
                                    sql.SQL(p.rstrip("*")) for p in sorted(to_grant)
                                ),
                                keyword,
                                identifier,
                                sql.Identifier(group),
                            )
                        )

    def grant_database_privileges(self, group: str, privileges: Set[str]):
        """Concede privilégios de banco ao grupo especificado.

        A implementação lê os privilégios atuais concedidos ao ``group`` e
        calcula as diferenças em relação ao conjunto desejado. Somente as
        diferenças são aplicadas via ``GRANT``/``REVOKE``, preservando quaisquer
        privilégios fora da "fronteira" definida pelo ``PRIVILEGE_WHITELIST``.
        """

        base_privs = {p.rstrip("*") for p in privileges}
        invalid = base_privs - PRIVILEGE_WHITELIST["DATABASE"]
        if invalid:
            raise ValueError(
                f"Privilégios inválidos para DATABASE: {', '.join(sorted(invalid))}"
            )

        dbname = self.conn.get_dsn_parameters().get("dbname")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.privilege_type, a.is_grantable
                FROM pg_database d
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(d.datacl, acldefault('d', d.datdba))
                ) AS a
                JOIN pg_roles gr ON gr.oid = a.grantee
                WHERE d.datname = current_database()
                  AND gr.rolname = %s
                """,
                (group,),
            )
            current = {
                priv + ("*" if grantable else "")
                for priv, grantable in cur.fetchall()
            }

            managed_current = {
                p for p in current if p.rstrip("*") in PRIVILEGE_WHITELIST["DATABASE"]
            }
            to_grant = privileges - managed_current
            to_revoke = managed_current - privileges

            if to_revoke:
                revoke_sql = sql.SQL("REVOKE {} ON DATABASE {} FROM {}").format(
                    sql.SQL(", ").join(
                        sql.SQL(p.rstrip("*")) for p in sorted(to_revoke)
                    ),
                    sql.Identifier(dbname),
                    sql.Identifier(group),
                )
                cur.execute(revoke_sql)

            if to_grant:
                plain = [p.rstrip("*") for p in sorted(to_grant) if not p.endswith("*")]
                star = [p.rstrip("*") for p in sorted(to_grant) if p.endswith("*")]
                if plain:
                    cur.execute(
                        sql.SQL("GRANT {} ON DATABASE {} TO {}").format(
                            sql.SQL(", ").join(sql.SQL(p) for p in plain),
                            sql.Identifier(dbname),
                            sql.Identifier(group),
                        )
                    )
                if star:
                    cur.execute(
                        sql.SQL(
                            "GRANT {} ON DATABASE {} TO {} WITH GRANT OPTION"
                        ).format(
                            sql.SQL(", ").join(sql.SQL(p) for p in star),
                            sql.Identifier(dbname),
                            sql.Identifier(group),
                        )
                    )

    def grant_schema_privileges(self, group: str, schema: str, privileges: Set[str]):
        """Concede privilégios de schema ao grupo informado."""
        logger.debug(f"grant_schema_privileges called: group={group}, schema={schema}, privileges={privileges}")
        
        base_privs = {p.rstrip("*") for p in privileges}
        invalid = base_privs - PRIVILEGE_WHITELIST["SCHEMA"]
        if invalid:
            raise ValueError(
                f"Privilégios inválidos para SCHEMA: {', '.join(sorted(invalid))}"
            )

        identifier = sql.Identifier(schema)
        with self.conn.cursor() as cur:
            # Obtém os privilégios atuais diretamente no banco via pg_catalog
            cur.execute(
                """
                SELECT a.privilege_type, a.is_grantable
                FROM pg_namespace n
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(n.nspacl, acldefault('n', n.nspowner))
                ) AS a
                JOIN pg_roles r ON r.oid = a.grantee
                WHERE r.rolname = %s AND n.nspname = %s
                """,
                (group, schema),
            )
            current = {
                priv + ("*" if grantable else "") for priv, grantable in cur.fetchall()
            }
            logger.debug(
                "Existing schema privileges for %s on %s: %s", group, schema, current
            )

            # Considera apenas privilégios gerenciados por este módulo
            managed_current = {
                p for p in current if p.rstrip("*") in PRIVILEGE_WHITELIST["SCHEMA"]
            }
            to_grant = privileges - managed_current
            to_revoke = managed_current - privileges

            if to_revoke:
                revoke_sql = sql.SQL("REVOKE {} ON SCHEMA {} FROM {}").format(
                    sql.SQL(", ").join(
                        sql.SQL(p.rstrip("*")) for p in sorted(to_revoke)
                    ),
                    identifier,
                    sql.Identifier(group),
                )
                try:
                    debug_sql = revoke_sql.as_string(cur)
                except Exception:
                    debug_sql = str(revoke_sql)
                logger.debug(f"Executing REVOKE: {debug_sql}")
                cur.execute(revoke_sql)

            if to_grant:
                plain = [p.rstrip("*") for p in sorted(to_grant) if not p.endswith("*")]
                star = [p.rstrip("*") for p in sorted(to_grant) if p.endswith("*")]
                if plain:
                    grant_sql = sql.SQL("GRANT {} ON SCHEMA {} TO {}").format(
                        sql.SQL(", ").join(sql.SQL(p) for p in plain),
                        identifier,
                        sql.Identifier(group),
                    )
                    try:
                        debug_sql = grant_sql.as_string(cur)
                    except Exception:
                        debug_sql = str(grant_sql)
                    logger.debug(f"Executing GRANT: {debug_sql}")
                    cur.execute(grant_sql)
                if star:
                    grant_sql = sql.SQL(
                        "GRANT {} ON SCHEMA {} TO {} WITH GRANT OPTION"
                    ).format(
                        sql.SQL(", ").join(sql.SQL(p) for p in star),
                        identifier,
                        sql.Identifier(group),
                    )
                    try:
                        debug_sql = grant_sql.as_string(cur)
                    except Exception:
                        debug_sql = str(grant_sql)
                    logger.debug(f"Executing GRANT (WGO): {debug_sql}")
                    cur.execute(grant_sql)

            if to_grant or to_revoke:
                logger.info(
                    "Updated schema privileges on %s for %s: +%s -%s",
                    schema,
                    group,
                    to_grant,
                    to_revoke,
                )
            else:
                logger.info(
                    "No schema privilege changes required on %s for %s",
                    schema,
                    group,
                )

        # Força commit se não estiver em transação
        if not getattr(self.conn, "autocommit", False):
            self.conn.commit()
    # ---------------------------------------------------------------
    # Consultas de privilégios de schema e default privileges futuros
    # ---------------------------------------------------------------
    def get_schema_privileges(self, role: str) -> Dict[str, Set[str]]:
        """Retorna {'schema': {'USAGE','CREATE'}} para privilégios diretos de schema do role.
        
        Versão super-robusta que nunca falha com IndexError.
        """
        out: Dict[str, Set[str]] = {}
        
        try:
            with self.conn.cursor() as cur:
                logger.debug(f"=== get_schema_privileges START for role: '{role}' ===")
                
                # Lista todos os schemas primeiro
                cur.execute(
                    """
                    SELECT nspname FROM pg_namespace 
                    WHERE nspname NOT LIKE 'pg\\_%' 
                      AND nspname <> 'information_schema'
                    ORDER BY nspname
                    """
                )
                schemas = []
                for row in cur.fetchall():
                    try:
                        if row:
                            schemas.append(row[0])
                    except Exception:
                        continue
                logger.debug(f"Found schemas: {schemas}")
                
                # Para cada schema, verifica privilégios individualmente
                for schema in schemas:
                    try:
                        # Verifica USAGE
                        cur.execute("SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema))
                        has_usage = cur.fetchone()[0]
                        
                        # Verifica CREATE  
                        cur.execute("SELECT has_schema_privilege(%s, %s, 'CREATE')", (role, schema))
                        has_create = cur.fetchone()[0]
                        
                        # Monta resultado
                        privs = set()
                        if has_usage:
                            privs.add('USAGE')
                        if has_create:
                            privs.add('CREATE')
                            
                        if privs:
                            out[schema] = privs
                            logger.debug(f"Schema '{schema}': {privs} for role '{role}'")
                            
                    except Exception as e:
                        logger.debug(f"Error checking privileges for schema '{schema}': {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Erro ao consultar privilégios de schema para role '{role}': {e}")
            # Retorna vazio em caso de erro, mas nunca quebra
            return {}
            
        logger.debug(f"=== get_schema_privileges END: {out} ===")
        return out

    def get_default_privileges(
        self,
        owner: str | None = None,
        objtype: str = "r",
        schema: str | None = None,
    ) -> Dict[str, Dict[str, Set[str]]]:
        """Return default privileges for future objects.

        Parameters
        ----------
        owner: str | None
            Filter by future object owner (``defaclrole``). If ``None`` return
            defaults for all owners.
        objtype: str
            PostgreSQL object type code (r: tables, S: sequences, f: functions,
            T: types, n: schemas). Defaults to ``'r'``.
        schema: str | None
            Filter by schema name (``defaclnamespace``) when ``IN SCHEMA`` is
            used. If ``None`` return defaults for all schemas.
        """

        params: Dict[str, object] = {"objtype": objtype}
        filters = ["d.defaclobjtype = %(objtype)s"]
        if owner:
            filters.append("r.rolname = %(owner)s")
            params["owner"] = owner
        if schema:
            filters.append("n.nspname = %(schema)s")
            params["schema"] = schema

        sql_query = (
            """
            SELECT r.rolname AS owner_role,
                   n.nspname AS schema,
                   COALESCE(gr.rolname, 'PUBLIC') AS grantee,
                   a.privilege_type,
                   a.is_grantable
            FROM pg_default_acl d
            JOIN pg_roles r ON r.oid = d.defaclrole
            JOIN pg_namespace n ON n.oid = d.defaclnamespace
            CROSS JOIN LATERAL aclexplode(d.defaclacl) AS a
            LEFT JOIN pg_roles gr ON gr.oid = a.grantee
            WHERE {where}
            ORDER BY n.nspname
            """.format(where=" AND ".join(filters))
        )

        result: Dict[str, Dict[str, Set[str]]] = {}
        meta_owner: Dict[str, str] = {}

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql_query, params)
                rows = cur.fetchall()

            for owner_role, schema_name, grantee, priv, grantable in rows:
                meta_owner[schema_name] = owner_role
                privname = priv + ("*" if grantable else "")
                result.setdefault(schema_name, {}).setdefault(grantee, set()).add(
                    privname
                )
        except Exception as e:
            logger.warning("Erro ao consultar default privileges: %s", e)
            return {}

        result["_meta"] = {"owner_roles": meta_owner}
        return result

    def get_object_dependencies(self, schema: str, objname: str) -> List[tuple[str, str]]:
        """Return list of dependent objects for a given table/view.

        The function queries ``pg_depend`` joined with ``pg_rewrite`` and
        ``pg_class`` to find views (or other objects) that depend on the
        target object. It is intentionally minimal and returns a list of
        ``(schema, name)`` tuples for each dependent object found. Any rows
        that do not contain both schema and object name are ignored so the
        method is robust against unexpected adapter behaviour.
        """

        query = """
            SELECT dep_n.nspname, dep_c.relname
            FROM pg_depend d
            JOIN pg_rewrite r ON r.oid = d.objid
            JOIN pg_class dep_c ON dep_c.oid = r.ev_class
            JOIN pg_namespace dep_n ON dep_n.oid = dep_c.relnamespace
            WHERE d.refobjid = (
                SELECT c.oid
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
            )
        """

        deps: List[tuple[str, str]] = []
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (schema, objname))
                for row in cur.fetchall():
                    try:
                        dep_schema, dep_name = row[0], row[1]
                    except Exception:
                        continue
                    if dep_schema and dep_name:
                        deps.append((dep_schema, dep_name))
        except Exception as e:
            logger.warning("Erro ao consultar dependências de %s.%s: %s", schema, objname, e)
            return []

        return deps

    def get_default_table_privileges(self, role: str) -> Dict[str, Set[str]]:
        """Retorna os privilégios padrão para tabelas futuramente criadas em cada schema."""
        logger.debug(f"=== get_default_table_privileges START for role: '{role}' ===")
    
        out = {}
        try:
            with self.conn.cursor() as cur:
                # Query direta usando aclexplode - muito mais confiável
                query = r"""
                    SELECT
                        n.nspname AS schema_name,
                        a.privilege_type
                    FROM
                        pg_default_acl t
                        JOIN pg_roles r ON t.defaclrole = r.oid
                        JOIN pg_namespace n ON t.defaclnamespace = n.oid,
                        LATERAL aclexplode(t.defaclacl) AS a
                    WHERE 
                        pg_get_userbyid(a.grantee) = %s
                        AND t.defaclobjtype = 'r'  -- 'r' para tabelas
                        AND n.nspname NOT LIKE 'pg\_%' ESCAPE '\'
                        AND n.nspname <> 'information_schema'
                    ORDER BY 
                        n.nspname
                """
                
                logger.debug(f"Executando query: {query} com parâmetro: {role}")
                cur.execute(query, (role,))
                
                for schema, priv in cur.fetchall():
                    if priv in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                        if schema not in out:
                            out[schema] = set()
                        out[schema].add(priv)
                        logger.debug(f"✓ Found default privilege: {schema}.{priv} for {role}")
    
        except Exception as e:
            logger.exception(f"Erro ao consultar privilégios default para role '{role}'")
    
        logger.debug(f"=== get_default_table_privileges END: {out} ===")
        return out

    def alter_default_privileges(
        self, group: str, schema: str, obj_type: str, privileges: Set[str], for_role: str = None
    ):
        """Altera os privilégios padrão para objetos futuros em um schema."""
        logger.debug(f"=== alter_default_privileges START ===")
        logger.debug(f"group={group}, schema={schema}, obj_type={obj_type}, privileges={privileges}, for_role={for_role}")

        # Validações
        if obj_type not in OBJECT_TYPES:
            raise ValueError(f"Tipo de objeto inválido: {obj_type}")

        # Mapeia para nome SQL e código de objeto
        obj_sql_name = OBJECT_TYPE_MAPS.get(obj_type, obj_type.upper())
        code = OBJECT_TYPE_CODES.get(obj_type)

        # Consulta privilégios atuais
        existing = (
            self.get_default_privileges(owner=for_role, objtype=code, schema=schema)
            .get(schema, {})
            .get(group, set())
        )
        desired = set(privileges)
        grant_set = desired - existing
        revoke_set = existing - desired
        logger.debug(f"existing={existing}, desired={desired}, grant_set={grant_set}, revoke_set={revoke_set}")
        if not grant_set and not revoke_set:
            logger.debug("Default privileges already set; no-op.")
            return True

        # Define cláusula FOR ROLE corretamente (identificador, não literal)
        if for_role:
            for_role_sql = sql.SQL("FOR ROLE {}" ).format(sql.Identifier(for_role))
        else:
            for_role_sql = sql.SQL("")

        with self.conn.cursor() as cur:
            if revoke_set:
                revoke_sql = sql.SQL(
                    "ALTER DEFAULT PRIVILEGES {for_role} IN SCHEMA {schema} REVOKE {privs} ON {obj_type} FROM {group}"
                ).format(
                    for_role=for_role_sql,
                    schema=sql.Identifier(schema),
                    privs=sql.SQL(", ").join(sql.SQL(p) for p in sorted(revoke_set)),
                    obj_type=sql.SQL(obj_sql_name),
                    group=sql.Identifier(group),
                )

                try:
                    sql_text = revoke_sql.as_string(cur)
                except Exception:
                    sql_text = str(revoke_sql)
                logger.debug(f"Executing REVOKE: {sql_text}")
                cur.execute(revoke_sql)

            if grant_set:
                grant_sql = sql.SQL(
                    "ALTER DEFAULT PRIVILEGES {for_role} IN SCHEMA {schema} GRANT {privs} ON {obj_type} TO {group}"
                ).format(
                    for_role=for_role_sql,
                    schema=sql.Identifier(schema),
                    privs=sql.SQL(", ").join(sql.SQL(p) for p in sorted(grant_set)),
                    obj_type=sql.SQL(obj_sql_name),
                    group=sql.Identifier(group),
                )

                try:
                    sql_text = grant_sql.as_string(cur)
                except Exception:
                    sql_text = str(grant_sql)
                logger.debug(f"Executing GRANT: {sql_text}")
                cur.execute(grant_sql)

        if grant_set or revoke_set:
            self.conn.commit()
            logger.info(
                f"\u2713 Applied default privileges: grant {grant_set} revoke {revoke_set} for {obj_type} in {schema} to {group}"
            )
        logger.debug(f"=== alter_default_privileges END ===")
        return True

    # Métodos de schema
    def create_schema(self, schema_name: str, owner: str | None = None):
        with self.conn.cursor() as cur:
            if owner:
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s", (owner,)
                )
                if not cur.fetchone():
                    cur.execute(
                        """
                        SELECT rolname FROM pg_roles
                        WHERE rolname NOT LIKE 'pg\\_%'
                          AND rolname NOT LIKE 'rls\\_%'
                        ORDER BY rolname
                        """
                    )
                    roles = ", ".join(row[0] for row in cur.fetchall())
                    raise ValueError(
                        f"Role '{owner}' não existe. Roles disponíveis: {roles}"
                    )
            query = sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
            if owner:
                query += sql.SQL(" AUTHORIZATION {}").format(sql.Identifier(owner))
            cur.execute(query)

    def drop_schema(self, schema_name: str, cascade: bool = False):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("DROP SCHEMA {} {}").format(
                    sql.Identifier(schema_name),
                    sql.SQL("CASCADE") if cascade else sql.SQL("RESTRICT"),
                )
            )

    def alter_schema_owner(self, schema_name: str, new_owner: str):
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(new_owner),
                )
            )

    def list_schemas(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT nspname
                FROM pg_namespace
                WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY nspname
                """
            )
            return [row[0] for row in cur.fetchall()]

    def enable_postgis(self, schema_name: str):
        """Garante que a extensão PostGIS esteja disponível no schema informado.

        - Verifica se a extensão já existe e, em caso afirmativo, obtém o schema
          onde está instalada.
        - Evita recriar a extensão caso ela já exista.
        - Configura ``search_path`` do *role* e do banco para incluir o schema da
          extensão.
        """

        with self.conn.cursor() as cur:
            # Verifica se a extensão já está instalada e em qual schema
            cur.execute(
                """
                SELECT e.extname, n.nspname
                FROM pg_extension e
                JOIN pg_namespace n ON e.extnamespace = n.oid
                WHERE e.extname = 'postgis'
                """
            )
            row = cur.fetchone()

            if row:
                ext_schema = row[1]
            else:
                # Cria a extensão caso ainda não exista
                cur.execute(
                    sql.SQL("CREATE EXTENSION IF NOT EXISTS postgis SCHEMA {}").format(
                        sql.Identifier(schema_name)
                    )
                )
                ext_schema = schema_name

            # Configura search_path do role e do banco para incluir o schema da extensão
            cur.execute("SELECT current_setting('search_path')")
            current_path = cur.fetchone()[0]
            paths = [p.strip() for p in current_path.split(',') if p]
            if ext_schema not in paths:
                new_path = f"{current_path},{ext_schema}" if current_path else ext_schema

                params = self.conn.get_dsn_parameters()
                role = params.get('user')
                dbname = params.get('dbname')

                if role:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} SET search_path = %s").format(
                            sql.Identifier(role)
                        ),
                        (new_path,)
                    )

                if dbname:
                    cur.execute(
                        sql.SQL("ALTER DATABASE {} SET search_path = %s").format(
                            sql.Identifier(dbname)
                        ),
                        (new_path,)
                    )

