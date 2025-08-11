-- 005_default_privileges.sql
-- Usar somente se não houver superusuário. Exemplo para um aluno específico.

DO $$
DECLARE u text := 'aluno_exemplo'; BEGIN
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO %I', u, 'GEO2_2025', lower('GEO2_2025') || '_leitor');
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT INSERT, UPDATE, DELETE ON TABLES TO %I', u, 'GEO2_2025', lower('GEO2_2025') || '_colab');
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO %I', u, 'GEO2_2025', lower('GEO2_2025') || '_leitor');
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I', u, 'GEO2_2025', lower('GEO2_2025') || '_colab');
END$$;
