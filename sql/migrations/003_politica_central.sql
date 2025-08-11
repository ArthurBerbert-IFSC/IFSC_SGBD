-- 003_politica_central.sql
-- Instala a política central (Event Trigger) que aplica GRANT automaticamente ao criar objetos.

CREATE SCHEMA IF NOT EXISTS admin;  -- owner: superusuário conectado

CREATE TABLE IF NOT EXISTS admin.acl_schemas(
  schema_name     text PRIMARY KEY,
  allow_functions boolean NOT NULL DEFAULT false,  -- libera EXECUTE em funções
  use_colab       boolean NOT NULL DEFAULT true    -- concede DML ao papel _colab
);

-- Exemplo de registro (ajustar por turma):
-- INSERT INTO admin.acl_schemas(schema_name, allow_functions, use_colab)
-- VALUES ('GEO2_2025', false, true)
-- ON CONFLICT (schema_name) DO UPDATE
--   SET allow_functions = EXCLUDED.allow_functions,
--       use_colab       = EXCLUDED.use_colab;

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

DROP EVENT TRIGGER IF EXISTS trg_apply_acl_on_create;
CREATE EVENT TRIGGER trg_apply_acl_on_create
  ON ddl_command_end
  WHEN TAG IN ('CREATE TABLE','CREATE TABLE AS',
               'CREATE SEQUENCE',
               'CREATE VIEW','CREATE MATERIALIZED VIEW',
               'CREATE FUNCTION')
  EXECUTE FUNCTION admin.apply_acl_on_create();
