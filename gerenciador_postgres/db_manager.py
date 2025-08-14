import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection
from contextlib import contextmanager
from .data_models import User, Group
from typing import Optional, List, Dict, Set, Callable
import logging

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

    def find_user_by_name(self, username: str) -> Optional[User]:
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
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = true
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]

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
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT g.rolname
                FROM pg_auth_members m
                JOIN pg_roles u ON m.member = u.oid
                JOIN pg_roles g ON m.roleid = g.oid
                WHERE u.rolname = %s
                ORDER BY g.rolname
            """, (username,))
            return [row[0] for row in cur.fetchall()]

    def list_groups(self) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolcanlogin = false
                  AND rolname NOT LIKE 'pg\\_%'
                  AND rolname NOT LIKE 'rls\\_%'
                  AND rolname <> 'postgres'
                ORDER BY rolname
            """)
            return [row[0] for row in cur.fetchall()]

    def list_roles(self) -> List[str]:
        """Retorna todos os roles disponíveis (usuários e grupos)."""
        with self.conn.cursor() as cur:
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

        with self.conn.cursor() as cur:
            cur.execute(sql_query, params)
            result: Dict[str, List[str]] = {schema: [] for schema in schemas}
            for schema, table in cur.fetchall():
                result.setdefault(schema, []).append(table)
            return result

    def get_group_privileges(self, group: str) -> Dict[str, Dict[str, Set[str]]]:
        """Retorna os privilégios de tabela concedidos a um grupo."""
        query = (
            "SELECT table_schema, table_name, privilege_type "
            "FROM information_schema.role_table_grants "
            "WHERE grantee = %s"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, (group,))
            result: Dict[str, Dict[str, Set[str]]] = {}
            for schema, table, priv in cur.fetchall():
                result.setdefault(schema, {}).setdefault(table, set()).add(priv)
            return result

    def apply_group_privileges(
        self,
        group: str,
        privileges: Dict[str, Dict[str, Set[str]]],
        obj_type: str = "TABLE",
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

        with self.conn.cursor() as cur:
            for schema, objects in privileges.items():
                for name, perms in objects.items():
                    invalid = set(perms) - allowed
                    if invalid:
                        raise ValueError(
                            f"Privilégios inválidos para {obj_type}: {', '.join(sorted(invalid))}"
                        )
                    identifier = sql.Identifier(schema, name)
                    cur.execute(
                        sql.SQL(
                            "REVOKE ALL PRIVILEGES ON {} {} FROM {}"
                        ).format(keyword, identifier, sql.Identifier(group))
                    )
                    if perms:
                        cur.execute(
                            sql.SQL("GRANT {} ON {} {} TO {}").format(
                                sql.SQL(", ").join(sql.SQL(p) for p in sorted(perms)),
                                keyword,
                                identifier,
                                sql.Identifier(group),
                            )
                        )

    def grant_database_privileges(self, group: str, privileges: Set[str]):
        """Concede privilégios de banco ao grupo especificado.

        Revoga primeiro todos os privilégios padrão e em seguida concede
        aqueles informados em ``privileges``.
        """
        invalid = set(privileges) - PRIVILEGE_WHITELIST["DATABASE"]
        if invalid:
            raise ValueError(
                f"Privilégios inválidos para DATABASE: {', '.join(sorted(invalid))}"
            )

        dbname = self.conn.get_dsn_parameters().get("dbname")
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}" ).format(
                    sql.Identifier(dbname), sql.Identifier(group)
                )
            )
            if privileges:
                cur.execute(
                    sql.SQL("GRANT {} ON DATABASE {} TO {}" ).format(
                        sql.SQL(", ").join(sql.SQL(p) for p in sorted(privileges)),
                        sql.Identifier(dbname),
                        sql.Identifier(group),
                    )
                )

    def grant_schema_privileges(self, group: str, schema: str, privileges: Set[str]):
        """Concede privilégios de schema ao grupo informado."""
        invalid = set(privileges) - PRIVILEGE_WHITELIST["SCHEMA"]
        if invalid:
            raise ValueError(
                f"Privilégios inválidos para SCHEMA: {', '.join(sorted(invalid))}"
            )

        identifier = sql.Identifier(schema)
        with self.conn.cursor() as cur:
            cur.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {}" ).format(
                    identifier, sql.Identifier(group)
                )
            )
            if privileges:
                cur.execute(
                    sql.SQL("GRANT {} ON SCHEMA {} TO {}" ).format(
                        sql.SQL(", ").join(sql.SQL(p) for p in sorted(privileges)),
                        identifier,
                        sql.Identifier(group),
                    )
                )
    # ---------------------------------------------------------------
    # Consultas de privilégios de schema e default privileges futuros
    # ---------------------------------------------------------------
    def get_schema_privileges(self, role: str) -> Dict[str, Set[str]]:
        """Retorna {'schema': {'USAGE','CREATE'}} para privilégios diretos de schema do role."""
        out: Dict[str, Set[str]] = {}
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, privilege_type
                FROM information_schema.schema_privileges
                WHERE grantee = %s
                  AND table_schema NOT LIKE 'pg\\_%'
                  AND table_schema <> 'information_schema'
                ORDER BY table_schema
                """,
                (role,),
            )
            # Some database adapters may yield rows with fewer columns or a
            # non-sequence type.  Safely extract the expected values and skip
            # anything that doesn't match the ``(schema, privilege)`` format.
            for row in cur.fetchall():
                try:
                    schema, privilege = row[0], row[1]
                except (IndexError, TypeError):
                    # Skip malformed or unexpected row formats instead of
                    # raising an error that would break the UI.
                    continue
                out.setdefault(schema, set()).add(privilege)
        return out

    def get_default_table_privileges(self, role: str) -> Dict[str, Set[str]]:
        """Retorna default privileges (ALTER DEFAULT PRIVILEGES) para futuras tabelas por schema concedidos ao role."""
        code_map = {'r': 'SELECT', 'a': 'INSERT', 'w': 'UPDATE', 'd': 'DELETE'}
        out: Dict[str, Set[str]] = {}
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT n.nspname, d.defaclacl
                FROM pg_default_acl d
                JOIN pg_namespace n ON n.oid = d.defaclnamespace
                WHERE d.defaclobjtype = 'r'
                """
            )
            rows = cur.fetchall()
            import re
            pattern = re.compile(r"^(?P<grantee>[^=]+)=(?P<privs>[^/]*)/.*$")
            for schema, acl_array in rows:
                if not acl_array:
                    continue
                for acl in acl_array:
                    m = pattern.match(acl)
                    if not m:
                        continue
                    grantee = m.group('grantee')
                    privcodes = m.group('privs')
                    if grantee == role:
                        mapped = {code_map[c] for c in privcodes if c in code_map}
                        if mapped:
                            out.setdefault(schema, set()).update(mapped)
        return out

    def alter_default_privileges(
        self, group: str, schema: str, obj_type: str, privileges: Set[str], *, for_role: str | None = None
    ):
        """Atualiza ``ALTER DEFAULT PRIVILEGES`` para novos objetos.

        Parameters
        ----------
        group : str
            Role a receber os privilégios padrão.
        schema : str
            Schema onde os objetos serão criados.
        obj_type : str
            Tipo de objeto (``tables``, ``sequences``, ``functions`` ou ``types``).
        privileges : Set[str]
            Conjunto de privilégios a conceder. Se vazio, remove todos.
        """

        type_map = {
            "tables": sql.SQL("TABLES"),
            "sequences": sql.SQL("SEQUENCES"),
            "functions": sql.SQL("FUNCTIONS"),
            "types": sql.SQL("TYPES"),
        }
        if obj_type not in type_map:
            raise ValueError(
                "obj_type deve ser 'tables', 'sequences', 'functions' ou 'types'"
            )

        whitelist_key = obj_type.rstrip("s").upper()
        invalid = set(privileges) - PRIVILEGE_WHITELIST[whitelist_key]
        if invalid:
            raise ValueError(
                f"Privilégios inválidos para {whitelist_key}: {', '.join(sorted(invalid))}"
            )

        identifier = sql.Identifier(schema)
        obj_keyword = type_map[obj_type]
        with self.conn.cursor() as cur:
            # Remove privilégios anteriores
            if for_role:
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} REVOKE ALL ON {} FROM {}"
                    ).format(sql.Identifier(for_role), identifier, obj_keyword, sql.Identifier(group))
                )
            else:
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL ON {} FROM {}"
                    ).format(identifier, obj_keyword, sql.Identifier(group))
                )
            if privileges:
                if for_role:
                    cur.execute(
                        sql.SQL(
                            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT {} ON {} TO {}"
                        ).format(
                            sql.Identifier(for_role),
                            identifier,
                            sql.SQL(", ").join(sql.SQL(p) for p in sorted(privileges)),
                            obj_keyword,
                            sql.Identifier(group),
                        )
                    )
                else:
                    cur.execute(
                        sql.SQL(
                            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT {} ON {} TO {}"
                        ).format(
                            identifier,
                            sql.SQL(", ").join(sql.SQL(p) for p in sorted(privileges)),
                            obj_keyword,
                            sql.Identifier(group),
                        )
                    )

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
            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name
            """)
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

