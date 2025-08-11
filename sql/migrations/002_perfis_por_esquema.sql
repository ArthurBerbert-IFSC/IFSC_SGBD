-- 002_perfis_por_esquema.sql

DO $$
DECLARE
    s_leitor text := lower('GEO2_2025') || '_leitor';
    s_autor  text := lower('GEO2_2025') || '_autor';
    s_colab  text := lower('GEO2_2025') || '_colab';
    s_gestor text := lower('GEO2_2025') || '_gestor';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = s_leitor) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', s_leitor);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = s_autor) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', s_autor);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = s_colab) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', s_colab);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = s_gestor) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', s_gestor);
    END IF;
END$$;

-- Cria o schema com owner = <schema>_gestor
DO $$
DECLARE s_gestor text := lower('GEO2_2025') || '_gestor'; BEGIN
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I', 'GEO2_2025', s_gestor);
END$$;

-- Privilégios no schema
DO $$
DECLARE
    s_leitor text := lower('GEO2_2025') || '_leitor';
    s_autor  text := lower('GEO2_2025') || '_autor';
    s_colab  text := lower('GEO2_2025') || '_colab';
    s_gestor text := lower('GEO2_2025') || '_gestor';
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I, %I, %I', 'GEO2_2025', s_leitor, s_autor, s_colab);
    EXECUTE format('GRANT CREATE ON SCHEMA %I TO %I, %I', 'GEO2_2025', s_autor, s_colab);
    EXECUTE format('GRANT ALL    ON SCHEMA %I TO %I', 'GEO2_2025', s_gestor);
END$$;

-- Concede CONNECT no banco aos papéis do esquema
DO $$
DECLARE
    dbname  text := 'NOME_DO_BANCO';
    s_leitor text := lower('GEO2_2025') || '_leitor';
    s_autor  text := lower('GEO2_2025') || '_autor';
    s_colab  text := lower('GEO2_2025') || '_colab';
    s_gestor text := lower('GEO2_2025') || '_gestor';
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I, %I, %I, %I', dbname, s_leitor, s_autor, s_colab, s_gestor);
END$$;
