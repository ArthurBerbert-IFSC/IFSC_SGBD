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

Para permitir que outro grupo crie schemas, edite o valor de `schema_creation_group` em `config/config.yml` e reinicie a aplicação.

O caminho informado em `log_path` é convertido para absoluto a partir de `BASE_DIR`, permitindo o uso de caminhos relativos.

Para sobrepor completamente as configurações, defina a variável de ambiente `IFSC_SGBD_CONFIG_FILE` apontando para um arquivo YAML alternativo ou edite o arquivo `config/config.yml` local.

Senhas de banco de dados **não** devem ser armazenadas no arquivo de configuração. 
O `ConnectionManager` buscará a senha a partir da variável de ambiente 
`<NOME_DO_PERFIL>_PASSWORD` (por exemplo, `LOCAL_PASSWORD`) ou do serviço 
`keyring` configurado para o usuário correspondente.

## Execução
Para iniciar a interface gráfica do gerenciador, execute:
```bash
python Rodar.py
```

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
