-- 004_reconciliar_legado.sql
-- Substituir GEO2_2025 pelo schema alvo.

DO $$
DECLARE
    s_leitor text := lower('GEO2_2025') || '_leitor';
    s_colab  text := lower('GEO2_2025') || '_colab';
BEGIN
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', 'GEO2_2025', s_leitor);
    EXECUTE format('GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', 'GEO2_2025', s_colab);
    EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I', 'GEO2_2025', s_leitor);
    EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO %I', 'GEO2_2025', s_colab);
END$$;
