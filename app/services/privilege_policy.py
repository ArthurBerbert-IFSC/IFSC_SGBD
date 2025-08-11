# app/services/privilege_policy.py
from __future__ import annotations
import re
import unicodedata
from contextlib import contextmanager
from typing import Optional, List, Dict

class PrivilegePolicyService:
    def __init__(self, conn):
        self.conn = conn  # conexão DB-API com autocommit desabilitado

    # --------------------- utilidades ---------------------
    @contextmanager
    def _tx(self):
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def _current_database(self) -> str:
        with self._tx() as cur:
            cur.execute("SELECT current_database()")
            (db,) = cur.fetchone()
            return db

    @staticmethod
    def _qident(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    @staticmethod
    def _role_names_for_schema(schema: str) -> Dict[str, str]:
        s = schema.lower()
        return {
            "leitor": f"{s}_leitor",
            "autor": f"{s}_autor",
            "colab": f"{s}_colab",
            "gestor": f"{s}_gestor",
        }

    def generate_username(self, full_name: str, fallback_suffix: str = "") -> str:
        def slug(s: str) -> str:
            s = unicodedata.normalize('NFD', s)
            s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
            s = re.sub(r"[^a-zA-Z0-9\s\-_.]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower()
        s = slug(full_name)
        parts = s.split()
        if not parts:
            base = "aluno"
        elif len(parts) == 1:
            base = parts[0]
        else:
            base = f"{parts[0]}.{parts[-1]}"  # nome.sobrenome
        if fallback_suffix:
            base = f"{base}.{fallback_suffix}"
        candidate = base
        with self._tx() as cur:
            i = 1
            while True:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (candidate,))
                if cur.fetchone() is None:
                    return candidate
                i += 1
                candidate = f"{base}{i}"

    # --------------------- infraestrutura ---------------------
    def ensure_base_hardening(self) -> None:
        dbname = self._current_database()
        with self._tx() as cur:
            cur.execute(f"REVOKE CONNECT ON DATABASE {self._qident(dbname)} FROM PUBLIC;")
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC;")

    def policy_install(self) -> None:
        with self._tx() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS admin;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin.acl_schemas(
                  schema_name     text PRIMARY KEY,
                  allow_functions boolean NOT NULL DEFAULT false,
                  use_colab       boolean NOT NULL DEFAULT true
                );
                """
            )
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION admin.apply_acl_on_create()
                RETURNS event_trigger
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog
                AS $$
                DECLARE
                  rec record;
                  sname text;
                  leitor text;
                  colab  text;
                  cfg    record;
                BEGIN
                  FOR rec IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
                    sname := rec.schema_name;
                    IF sname IS NULL THEN CONTINUE; END IF;
                    SELECT * INTO cfg FROM admin.acl_schemas WHERE schema_name = sname;
                    IF NOT FOUND THEN CONTINUE; END IF;
                    leitor := lower(sname) || '_leitor';
                    colab  := lower(sname) || '_colab';
                    IF rec.object_type = 'table' THEN
                      EXECUTE format('GRANT SELECT ON TABLE %s TO %I', rec.object_identity, leitor);
                      IF cfg.use_colab THEN
                        EXECUTE format('GRANT INSERT, UPDATE, DELETE ON TABLE %s TO %I', rec.object_identity, colab);
                      END IF;
                    ELSIF rec.object_type = 'sequence' THEN
                      EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I', rec.object_identity, leitor);
                      IF cfg.use_colab THEN
                        EXECUTE format('GRANT USAGE, SELECT, UPDATE ON SEQUENCE %s TO %I', rec.object_identity, colab);
                      END IF;
                    ELSIF rec.object_type IN ('view','materialized view') THEN
                      EXECUTE format('GRANT SELECT ON %s TO %I', rec.object_identity, leitor);
                      IF cfg.use_colab THEN
                        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %s TO %I', rec.object_identity, colab);
                      END IF;
                    ELSIF rec.object_type = 'function' THEN
                      IF cfg.allow_functions THEN
                        EXECUTE format('GRANT EXECUTE ON %s TO %I', rec.object_identity, leitor);
                        IF cfg.use_colab THEN
                          EXECUTE format('GRANT EXECUTE ON %s TO %I', rec.object_identity, colab);
                        END IF;
                      END IF;
                    END IF;
                  END LOOP;
                END;
                $$;
                """
            )
            cur.execute(
                """
                DROP EVENT TRIGGER IF EXISTS trg_apply_acl_on_create;
                CREATE EVENT TRIGGER trg_apply_acl_on_create
                  ON ddl_command_end
                  WHEN TAG IN ('CREATE TABLE','CREATE TABLE AS',
                               'CREATE SEQUENCE',
                               'CREATE VIEW','CREATE MATERIALIZED VIEW',
                               'CREATE FUNCTION')
                  EXECUTE FUNCTION admin.apply_acl_on_create();
                """
            )

    def policy_add_schema(self, schema: str, allow_functions: bool = False, use_colab: bool = False) -> None:
        with self._tx() as cur:
            cur.execute(
                """
                INSERT INTO admin.acl_schemas(schema_name, allow_functions, use_colab)
                VALUES (%s, %s, %s)
                ON CONFLICT (schema_name) DO UPDATE
                  SET allow_functions = EXCLUDED.allow_functions,
                      use_colab       = EXCLUDED.use_colab;
                """,
                (schema, allow_functions, use_colab),
            )

    # --------------------- perfis por esquema ---------------------
    def create_schema_profiles(self, schema: str) -> None:
        roles = self._role_names_for_schema(schema)
        schema_q = self._qident(schema)
        with self._tx() as cur:
            for r in roles.values():
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (r,))
                if cur.fetchone() is None:
                    cur.execute(f"CREATE ROLE {self._qident(r)} NOLOGIN")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_q} AUTHORIZATION {self._qident(roles['gestor'])}")
            cur.execute(f"GRANT USAGE ON SCHEMA {schema_q} TO {self._qident(roles['leitor'])}, {self._qident(roles['autor'])}, {self._qident(roles['colab'])}")
            cur.execute(f"GRANT CREATE ON SCHEMA {schema_q} TO {self._qident(roles['autor'])}, {self._qident(roles['colab'])}")
            cur.execute(f"GRANT ALL    ON SCHEMA {schema_q} TO {self._qident(roles['gestor'])}")
            dbname = self._current_database()
            cur.execute(
                f"GRANT CONNECT ON DATABASE {self._qident(dbname)} TO {self._qident(roles['leitor'])}, {self._qident(roles['autor'])}, {self._qident(roles['colab'])}, {self._qident(roles['gestor'])}"
            )

    def reconcile_schema_privileges(self, schema: str) -> None:
        roles = self._role_names_for_schema(schema)
        schema_q = self._qident(schema)
        with self._tx() as cur:
            cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema_q} TO {self._qident(roles['leitor'])}")
            cur.execute(f"GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema_q} TO {self._qident(roles['colab'])}")
            cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema_q} TO {self._qident(roles['leitor'])}")
            cur.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {schema_q} TO {self._qident(roles['colab'])}")

    # --------------------- matrícula e expiração ---------------------
    def _create_login_if_missing(self, username: str, password: Optional[str]) -> None:
        with self._tx() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
            if cur.fetchone() is None:
                if password is None:
                    cur.execute(f"CREATE ROLE {self._qident(username)} LOGIN INHERIT")
                else:
                    cur.execute(f"CREATE ROLE {self._qident(username)} LOGIN INHERIT PASSWORD %s", (password,))

    def _grant_profile(self, schema: str, username: str, perfil: str) -> None:
        roles = self._role_names_for_schema(schema)
        with self._tx() as cur:
            if perfil.upper() == "LEITOR":
                cur.execute(f"GRANT {self._qident(roles['leitor'])} TO {self._qident(username)}")
            elif perfil.upper() == "AUTOR":
                cur.execute(f"GRANT {self._qident(roles['leitor'])} TO {self._qident(username)}")
                cur.execute(f"GRANT {self._qident(roles['autor'])}  TO {self._qident(username)}")
            elif perfil.upper() == "COLABORADOR":
                cur.execute(f"GRANT {self._qident(roles['colab'])} TO {self._qident(username)}")
            elif perfil.upper() == "GESTOR":
                cur.execute(f"GRANT {self._qident(roles['gestor'])} TO {self._qident(username)}")
            else:
                raise ValueError(f"Perfil desconhecido: {perfil}")

    def set_user_profile(self, schema: str, username: str, perfil: str) -> None:
        roles = self._role_names_for_schema(schema)
        with self._tx() as cur:
            for r in roles.values():
                cur.execute(f"REVOKE {self._qident(r)} FROM {self._qident(username)}")
        self._grant_profile(schema, username, perfil)

    def set_user_expiration(self, username: str, expires_at: Optional[str]) -> None:
        with self._tx() as cur:
            if expires_at:
                cur.execute(f"ALTER ROLE {self._qident(username)} VALID UNTIL %s", (expires_at,))
            else:
                cur.execute(f"ALTER ROLE {self._qident(username)} VALID UNTIL NULL")

    def enroll_users(self, schema: str, perfil: str, paste_text: str, default_expiration: Optional[str] = None) -> List[Dict]:
        results: List[Dict] = []
        lines = [ln.strip() for ln in paste_text.splitlines() if ln.strip()]
        for raw in lines:
            parts = re.split(r"\t+|\s{2,}", raw)
            if len(parts) < 3:
                results.append({"line": raw, "ok": False, "msg": "Linha inválida (esperado 3 colunas)"})
                continue
            _, matricula, nome = parts[0], parts[1], parts[2]
            username = self.generate_username(nome, fallback_suffix=matricula[-3:])
            try:
                self._create_login_if_missing(username, matricula)
                self._grant_profile(schema, username, perfil)
                if default_expiration:
                    self.set_user_expiration(username, default_expiration)
                results.append({"username": username, "senha": matricula, "ok": True, "msg": "matriculado"})
            except Exception as e:
                results.append({"username": username, "senha": matricula, "ok": False, "msg": str(e)})
        return results

    def check_trigger_health(self) -> Dict[str, bool]:
        out = {"function": False, "trigger": False}
        with self._tx() as cur:
            cur.execute("SELECT 1 FROM pg_proc WHERE proname='apply_acl_on_create' AND pg_catalog.pg_function_is_visible(oid)")
            out["function"] = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM pg_event_trigger WHERE evtname='trg_apply_acl_on_create'")
            out["trigger"] = cur.fetchone() is not None
        return out
