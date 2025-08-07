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
