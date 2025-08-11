-- 001_hardening.sql
-- Endurecimento básico do banco. Execute uma única vez por banco.

-- Substitua NOME_DO_BANCO pelo nome correto do banco
REVOKE CONNECT ON DATABASE "NOME_DO_BANCO" FROM PUBLIC;

-- Endurece o schema public (útil em bases herdadas)
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
