# Gerenciador PostgreSQL

## Objetivo
Aplicação em Python com interface gráfica (PyQt6) para facilitar a administração de um servidor PostgreSQL. O sistema permite gerenciar conexões, esquemas, papéis, auditoria de operações e outros recursos de bancos de dados de forma centralizada.

## Requisitos
- Python 3.10+
- PyQt6
- psycopg2-binary
- PyYAML
- pytest (para executar os testes)
- keyring
- python-dotenv (opcional para desenvolvimento)

## Instalação
1. Clone o repositório:
   ```bash
   git clone <url>
   cd IFSC_SGBD
   ```
2. (Opcional) Crie e ative um ambiente virtual.
3. Instale as dependências:
   ```bash
    pip install -r requirements.txt
    pip install pytest
    ```

## Configuração
O arquivo `config/config.yml` centraliza parâmetros do sistema. Nele é possível definir:

- `log_level`: nível de detalhamento dos logs.
- `log_path`: caminho do arquivo de log (relativo a `BASE_DIR`).
- `group_prefix`: prefixo obrigatório para nomes de grupos (padrão `"grp_"`).
- `schema_creation_group`: nome do grupo autorizado a criar schemas (padrão `"Professores"`).
- `connect_timeout`: tempo máximo (segundos) para tentar conectar ao banco (padrão `5`).

Os logs são configurados automaticamente na importação do pacote e podem ser
personalizados editando `config/config.yml`.

Para permitir que outro grupo crie schemas, edite o valor de `schema_creation_group` em `config/config.yml` e reinicie a aplicação.

O caminho informado em `log_path` é convertido para absoluto a partir de `BASE_DIR`, permitindo o uso de caminhos relativos.

Para sobrepor completamente as configurações, defina a variável de ambiente `IFSC_SGBD_CONFIG_FILE` apontando para um arquivo YAML alternativo ou edite o arquivo `config/config.yml` local.

Senhas de banco de dados **não** devem ser armazenadas no arquivo YAML.
O `ConnectionManager` buscará a senha na variável de ambiente
`<NOME_DO_PERFIL>_PASSWORD` (por exemplo, `REMOTO_PASSWORD`) ou no serviço
`keyring` configurado para o usuário correspondente.

```bash
# Exemplo com variável de ambiente
export REMOTO_PASSWORD="minha_senha"
```

```python
# Exemplo salvando no keyring
import keyring
keyring.set_password("IFSC_SGBD", "postgres", "minha_senha")
```

É proibido definir a chave `password` em perfis do `config.yml`.

## Execução
Para iniciar a interface gráfica do gerenciador, execute:
```bash
python Rodar.py
```

## Perfis na GUI

- Selecionar perfil existente pela combo.
- Salvar perfil: botão "Salvar" abre diálogo, solicita nome e grava sem senha.
- Apagar perfil: botão "Apagar" remove do YAML.
- Testar conexão: botão dedicado "Testar conexão".

Senhas nunca são salvas; use variável de ambiente `<PERFIL>_PASSWORD` ou o keyring (`IFSC_SGBD`, conta = usuário).

## Testes
Os testes automatizados estão no diretório `tests/`. Execute-os com:
```bash
pytest
```

## Contribuição
Contribuições são bem-vindas! Abra issues com sugestões ou problemas e envie pull requests com melhorias ou correções.

## Licença
Este projeto está licenciado sob os termos da [MIT License](LICENSE).

## Autoria
Projeto desenvolvido por Arthur Peixoto Berbert Lima.

## Pré-requisitos no servidor

Para que as conexões remotas funcionem, o DBA deve garantir:

- `listen_addresses='*'` no `postgresql.conf`.
- Entrada adequada no `pg_hba.conf` para a rede do cliente.
- Porta `5432/tcp` liberada no firewall.

## Validação rápida

1. **PG/psql (no servidor):**
   ```
   SHOW server_version;
   SELECT PostGIS_Version();
   ```

2. **Cliente (sem GUI):**
   ```
   # por perfil
   PERFIL_REMOTO_PASSWORD=suasenha python scripts/test_connection.py --profile Remoto
   # ad-hoc
   python scripts/test_connection.py --host 192.168.x.y --port 5432 --dbname db --user usr
   ```

3. **Cenários de falha (para checar mensagens):**
   - Host inválido;
   - Porta bloqueada;
   - Usuário/senha incorretos.

4. **GUI:**
   - Selecionar perfil; Testar conexão;
   - Editar campos → Salvar (novo nome) → reaparecer na combo;
   - Apagar perfil recém-criado;
   - Verificar logs/app.log sendo escrito.
