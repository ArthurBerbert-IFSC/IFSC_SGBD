import logging
from datetime import datetime
from typing import Dict, List, Optional

from psycopg2.extras import Json

from .db_manager import DBManager


class AuditManager:
    """Gerencia a auditoria das operações de permissões."""

    def __init__(self, dao: DBManager, logger: logging.Logger):
        self.dao = dao
        self.logger = logger
        self._ensure_audit_table()

    def _ensure_audit_table(self):
        """Cria a tabela de auditoria caso não exista."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auditoria_permissoes (
                        id SERIAL PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        actor VARCHAR(100) NOT NULL,
                        database_name VARCHAR(100) NOT NULL,
                        schema_name VARCHAR(100) NOT NULL,
                        contract_json JSONB,
                        diff_sql TEXT,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_auditoria_permissoes_applied_at
                        ON auditoria_permissoes(applied_at)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_auditoria_permissoes_actor
                        ON auditoria_permissoes(actor)
                    """
                )

            self.dao.conn.commit()
            self.logger.info("Tabela de auditoria inicializada com sucesso")
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"Erro ao inicializar tabela de auditoria: {e}")
            raise

    def log_operation(
        self,
        actor: str,
        database_name: str,
        schema_name: str,
        contract_json: Optional[Dict] = None,
        diff_sql: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Registra uma operação de auditoria de permissões."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auditoria_permissoes
                        (actor, database_name, schema_name, contract_json, diff_sql, success, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        actor,
                        database_name,
                        schema_name,
                        Json(contract_json) if contract_json else None,
                        diff_sql,
                        success,
                        error_message,
                    ),
                )

            # O commit deve ser controlado externamente pelo contexto
            # da transação principal. Dessa forma, em caso de falha na
            # operação principal, o registro de auditoria também será revertido.

        except Exception as e:
            self.logger.error(f"Erro ao registrar auditoria: {e}")
            # Não propagar erro de auditoria para não afetar operação principal

    def get_audit_logs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Retorna os registros de auditoria mais recentes."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, applied_at, actor, database_name, schema_name,
                           contract_json, diff_sql, success, error_message
                    FROM auditoria_permissoes
                    ORDER BY applied_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Erro ao consultar auditoria: {e}")
            return []

    def get_audit_stats(self) -> Dict:
        """Retorna estatísticas básicas da auditoria."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*),
                           SUM(CASE WHEN success THEN 1 ELSE 0 END)
                    FROM auditoria_permissoes
                    """
                )
                total, success_count = cur.fetchone()
                return {
                    "total_registros": total,
                    "sucessos": success_count,
                    "falhas": total - success_count,
                }
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas de auditoria: {e}")
            return {}

    def cleanup_old_logs(self, days_to_keep: int = 90):
        """Remove registros de auditoria antigos."""
        try:
            with self.dao.conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM auditoria_permissoes
                    WHERE applied_at < NOW() - INTERVAL '%s days'
                    """,
                    (days_to_keep,),
                )
                deleted_count = cur.rowcount
                self.dao.conn.commit()
                self.logger.info(
                    f"Limpeza de auditoria: {deleted_count} registros removidos"
                )
                return deleted_count
        except Exception as e:
            self.dao.conn.rollback()
            self.logger.error(f"Erro na limpeza de auditoria: {e}")
            raise

